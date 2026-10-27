from app import config

OK = {"prenom": "Elie", "age": "1", "cgu": "1", "ia": "1"}


def inscrire(client, email, **extra):
    return client.post("/inscription", data={**OK, "email": email, **extra})


def chemin(link):
    return link.replace(config.BASE_URL, "")


def connecter_admin(client, links):
    inscrire(client, "admin@exemple.fr")
    return client.get(chemin(links["admin@exemple.fr"][-1]), follow_redirects=False)


def test_les_trois_cases_sont_obligatoires(client, links):
    r = client.post("/inscription", data={"prenom": "Elie", "email": "a@b.fr", "age": "1", "cgu": "1"})
    assert r.status_code == 400
    assert "Cochez les cases encadrées" in r.text and r.text.count("check manquante") == 1  # la case IA, montree en rouge
    assert links == {}


def test_email_invalide_refuse(client):
    r = inscrire(client, "pas-un-email")
    assert r.status_code == 400


def test_nouvel_inscrit_va_en_liste_d_attente(client, links):
    r = inscrire(client, "Marie@Exemple.fr ")
    assert "Vous êtes sur la liste" in r.text
    assert links == {}  # aucun lien tant que le compte n'est pas accepte


def test_parcours_admin_complet(client, links):
    r = connecter_admin(client, links)
    assert r.status_code == 303 and r.headers["location"] == "/presentation"
    assert client.get("/accueil").status_code == 200

    # la presentation n'est montree qu'une fois
    client.post("/presentation/fin")
    client.post("/deconnexion")
    client.post("/connexion", data={"email": "admin@exemple.fr"})
    r = client.get(chemin(links["admin@exemple.fr"][-1]), follow_redirects=False)
    assert r.headers["location"] == "/accueil"


def test_lien_utilisable_une_seule_fois(client, links):
    connecter_admin(client, links)
    r = client.get(chemin(links["admin@exemple.fr"][-1]))
    assert r.status_code == 400 and "ne fonctionne plus" in r.text


def test_lien_expire(client, links, monkeypatch):
    monkeypatch.setattr(config, "LOGIN_TOKEN_MINUTES", -1)
    inscrire(client, "admin@exemple.fr")
    r = client.get(chemin(links["admin@exemple.fr"][-1]))
    assert r.status_code == 400


def test_pages_protegees_sans_session(client):
    r = client.get("/accueil", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"


def test_admin_accepte_la_liste_d_attente(client, links):
    inscrire(client, "marie@exemple.fr", partage="1")
    connecter_admin(client, links)
    page = client.get("/admin")
    assert "marie@exemple.fr" in page.text
    client.post("/admin/activer/1")  # marie, inscrite en premier
    assert len(links["marie@exemple.fr"]) == 1  # le lien part a l'acceptation


def test_admin_interdit_aux_autres(client, links):
    inscrire(client, "marie@exemple.fr")
    connecter_admin(client, links)
    client.post("/admin/activer/1")  # marie, inscrite en premier
    client.post("/deconnexion")
    client.get(chemin(links["marie@exemple.fr"][-1]))
    assert client.get("/admin").status_code == 404


def test_connexion_ne_revele_pas_les_comptes(client, links):
    r = client.post("/connexion", data={"email": "inconnu@exemple.fr"})
    assert r.status_code == 200 and "Vérifiez vos e-mails" in r.text
    assert links == {}


def test_limite_de_liens_par_heure(client, links):
    for _ in range(config.MAX_LINKS_PER_HOUR + 3):
        client.post("/connexion", data={"email": "admin@exemple.fr"}) if links else inscrire(client, "admin@exemple.fr")
    assert len(links["admin@exemple.fr"]) == config.MAX_LINKS_PER_HOUR


def test_envoi_rate_ne_compte_pas(client, monkeypatch):
    from app import auth as module_auth
    monkeypatch.setattr(module_auth, "send_login_email", lambda user, link: False)  # Brevo refuse tout
    for _ in range(config.MAX_LINKS_PER_HOUR + 2):
        client.post("/connexion", data={"email": "admin@exemple.fr"}) if _ else inscrire(client, "admin@exemple.fr")
    envoyes = []
    monkeypatch.setattr(module_auth, "send_login_email", lambda user, link: envoyes.append(link) or True)
    client.post("/connexion", data={"email": "admin@exemple.fr"})
    assert len(envoyes) == 1  # la limite n'a pas ete consommee par les echecs


def test_inscription_libre(client, links, monkeypatch):
    monkeypatch.setattr(config, "INSCRIPTION_LIBRE", True)
    r = inscrire(client, "lea@exemple.fr")
    assert "Vérifiez vos e-mails" in r.text and len(links["lea@exemple.fr"]) == 1  # le lien part tout de suite
    r = client.get(chemin(links["lea@exemple.fr"][-1]), follow_redirects=False)
    assert r.headers["location"] == "/presentation"


def test_ancienne_liste_d_attente_acceptee(client, links, monkeypatch):
    inscrire(client, "marie@exemple.fr")  # liste d'attente
    monkeypatch.setattr(config, "INSCRIPTION_LIBRE", True)
    client.post("/connexion", data={"email": "marie@exemple.fr"})
    assert len(links["marie@exemple.fr"]) == 1
    inscrire(client, "paul@exemple.fr")  # deja libre : actif tout de suite
    monkeypatch.setattr(config, "INSCRIPTION_LIBRE", False)
    inscrire(client, "zoe@exemple.fr")
    monkeypatch.setattr(config, "INSCRIPTION_LIBRE", True)
    from app import main
    main._accepter_la_liste_d_attente()  # au demarrage
    assert len(links["zoe@exemple.fr"]) == 1
