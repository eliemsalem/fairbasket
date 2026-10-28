from types import SimpleNamespace

from sqlalchemy import select

from app import assistant, config
from app.models import ExpressionApprise, LectureTicket, Question
from tests.test_stats import ticket
from tests.test_tickets import ALDI, _article, db, fausse_lecture, nouvel_utilisateur  # noqa: F401

ZONE = {"lat": 48.88, "lon": 2.37, "ville": "Paris"}


def test_le_code_comprend_les_questions_courantes():
    c = assistant.comprendre
    assert c("Où je peux trouver des pastilles pour le lave vaisselle les moins chères à côté de chez moi ?") == \
        ("prix", {"produit": "pastilles pour le lave vaisselle"})
    assert c("les oeufs bio sont moins chers où ?") == ("prix", {"produit": "oeufs bio"})
    assert c("Combien j'ai dépensé en fromage ce mois-ci ?") == ("depenses", {"rayon": "Fromages", "periode": "mois"})
    assert c("combien j ai depense pour le saumon") == ("depenses", {"produit": "saumon", "periode": "an"})
    assert c("Ajoute du lait à ma liste") == ("liste", {"produit": "lait"})
    assert c("Mon panier serait moins cher où ?") == ("panier", {})
    assert c("Quel temps fait-il ?") is None


# --- un faux Claude : des reponses preparees, rejouees dans l'ordre -----------------------------------------

def _usage(entree=1000, sortie=100, web=0):
    return SimpleNamespace(input_tokens=entree, output_tokens=sortie,
                           server_tool_use=SimpleNamespace(web_search_requests=web))


def _texte(t, urls=()):
    return SimpleNamespace(type="text", text=t, citations=[SimpleNamespace(url=u, title="Drive") for u in urls])


class FauxClaude:
    def __init__(self, *reponses):
        self.reponses, self.appels = list(reponses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.appels.append(kw)
        stop, contenu, usage = self.reponses.pop(0)
        return SimpleNamespace(stop_reason=stop, content=contenu, usage=usage, model="claude-haiku-5-5")


def test_prix_connu_repondu_par_le_code_sans_claude(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("X6 OEUFS CRF BIO", "Œufs bio ×6", 2.49)])
    ticket(db, u, 2, "Biocoop", "2026-10-15", [_article("OEUFS BIOCOOP 6", "Œufs bio ×6", 2.82)])
    client = FauxClaude()
    q = assistant.demander(db, u, "Où trouver des oeufs bio moins chers ?", ZONE, client=client)
    assert q.moteur == "code" and q.intention == "prix" and q.trouve and client.appels == []
    assert "Carrefour" in q.reponse and q.resultats and q.etapes[0]["outil"] == "chercher_prix"
    # la meme question juste apres : deja repondue
    assert assistant.demander(db, u, "où trouver des œufs bio moins chers", ZONE, client=client).moteur == "cache"


def test_prix_inconnu_claude_cherche_sur_le_web(db, monkeypatch):
    u = nouvel_utilisateur(db, "a@x.fr")
    client = FauxClaude(("end_turn", [_texte("Chez Leclerc Drive : 6,90 € les 40 pastilles.",
                                             ["https://drive.example/pastilles"])], _usage(web=1)))
    q = assistant.demander(db, u, "Où trouver des pastilles lave-vaisselle moins chères ?", ZONE, client=client)
    appel = client.appels[0]
    assert any(t.get("name") == "web_search" for t in appel["tools"])
    assert "rien trouvé" in appel["messages"][0]["content"]  # chercher_prix deja fait par le code
    assert q.moteur == "claude" and q.trouve and q.recherches_web == 1 and "Leclerc" in q.reponse
    assert q.sources == [{"url": "https://drive.example/pastilles", "titre": "Drive"}]
    assert q.cout_usd > 0.01  # la recherche web + les jetons


def test_claude_comprend_puis_le_code_a_appris(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("CHEVRE", "Bûche de chèvre", 3.10)])
    ticket(db, u, 2, "Monoprix", "2026-10-04", [_article("CHEVRE", "Bûche de chèvre", 3.60)])
    appel = SimpleNamespace(type="tool_use", id="t1", name="chercher_prix", input={"produit": "bûche de chèvre"})
    client = FauxClaude(("tool_use", [appel], _usage()), ("end_turn", [_texte("3,10 € chez Carrefour.")], _usage()))
    texte = "J'ai envie d'une bûche de chèvre, c'est où le mieux ?"
    q = assistant.demander(db, u, texte, ZONE, client=client)
    assert q.moteur == "claude" and q.trouve and q.intention == "prix" and q.etapes[0]["outil"] == "chercher_prix"
    assert db.scalar(select(ExpressionApprise)).parametres == {"produit": "bûche de chèvre"}
    # une autre personne pose la meme question : le code la comprend seul
    v = nouvel_utilisateur(db, "b@x.fr")
    q2 = assistant.demander(db, v, texte, ZONE, client=FauxClaude())
    assert q2.moteur == "appris" and q2.intention == "prix"
    # jugee pas utile : l'expression est oubliee
    assistant.noter_avis(db, q2, -1, "pas ça")
    assert db.scalar(select(ExpressionApprise)) is None and q2.commentaire == "pas ça"


def test_sans_budget_pas_de_claude(db, monkeypatch):
    monkeypatch.setattr(config, "ASSISTANT_BUDGET_USD", 0)
    u = nouvel_utilisateur(db, "a@x.fr")
    client = FauxClaude()
    q = assistant.demander(db, u, "Quel temps fait-il ?", ZONE, client=client)
    assert client.appels == [] and not q.trouve and "budget" in q.erreur and "pas compris" in q.reponse


def test_depenses_et_liste(db):
    u = nouvel_utilisateur(db, "a@x.fr")
    ticket(db, u, 1, "Carrefour", "2026-10-03", [_article("A", "Œufs bio ×6", 12.0)])
    q = assistant.demander(db, u, "Combien j'ai dépensé pour les oeufs ?", ZONE)
    assert q.moteur == "code" and q.trouve and "12,00" in q.reponse
    q = assistant.demander(db, u, "Ajoute du beurre à ma liste", ZONE)
    db.refresh(u)
    assert q.trouve and u.liste[-1].nom == "Beurre"


def test_page_reservee_puis_ouverte(client, links, monkeypatch):
    from tests.test_auth import connecter_admin
    connecter_admin(client, links)
    r = client.post("/assistant", data={"question": "Ajoute du lait à ma liste"})
    assert r.status_code == 200 and "est dans votre liste" in r.text
    assert "Demandez-moi" in client.get("/accueil").text
    page = client.get("/admin/assistant").text
    assert "Ajoute du lait" in page and "Sans Claude" in page
    assert '"intention": "liste"' in client.get("/admin/export/questions.jsonl").text
    monkeypatch.setattr(config, "ASSISTANT_POUR", "testeurs")
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    assert client.get("/assistant").status_code == 404


# --- base d'apprentissage des lectures ---------------------------------------------------------------------

def test_chaque_lecture_est_gardee_avec_ses_corrections(client, links, monkeypatch, tmp_path):
    from app.db import SessionLocal
    from app.models import User
    from app.tickets import TicketRefuse, enregistrer_ticket
    from tests.test_auth import connecter_admin
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    connecter_admin(client, links)
    with SessionLocal() as db:
        u = db.query(User).first()
        r = enregistrer_ticket(db, u, b"photo", "t.jpg", "image/jpeg", lire=fausse_lecture(ALDI)).receipt
        rid, item = r.id, r.items[0].id
        try:
            enregistrer_ticket(db, u, b"floue", "f.jpg", "image/jpeg", lire=fausse_lecture({"lisible": False}))
        except TicketRefuse:
            pass
    client.post(f"/tickets/{rid}/corriger", data={f"libelle_{item}": "OIGNONS ROUGES", f"montant_{item}": "1,05"})
    with SessionLocal() as db:
        ok, ratee = db.scalars(select(LectureTicket).order_by(LectureTicket.id)).all()
        assert ok.resultat == "ok" and ok.receipt_id == rid and ok.lu["enseigne"] == "Aldi" and ok.nb_articles == 3
        assert ok.nb_corrections == 1 and ok.corrige["articles"][0]["libelle"] == "OIGNONS ROUGES"
        assert ok.methode == "IA" and ok.tokens_entree == 1000
        assert ratee.resultat == "illisible" and ratee.receipt_id is None and ratee.fichier_chemin
        ratee_id = ratee.id
    assert client.get(f"/admin/lectures/{ratee_id}/fichier").content == b"floue"
    assert "Lecture des tickets" in client.get("/admin/lectures").text
    assert '"resultat": "illisible"' in client.get("/admin/export/lectures.jsonl").text
    # le compte supprime emporte ses lectures et ses questions
    client.post("/profil/supprimer", data={"confirmation": "SUPPRIMER"})
    with SessionLocal() as db:
        assert db.scalars(select(LectureTicket)).all() == [] and db.scalars(select(Question)).all() == []


def test_comparer_sans_aucun_prix_propose_la_recherche_en_ligne(client, links):
    from tests.test_auth import connecter_admin
    connecter_admin(client, links)
    page = client.get("/comparer?q=pastilles%20lave-vaisselle").text
    assert "Personne n&#39;a encore de prix" in page or "Personne n'a encore de prix" in page
    assert "Chercher les prix en ligne" in page and 'action="/assistant"' in page
    r = client.post("/assistant", data={"question": "Où trouver pastilles lave-vaisselle moins cher près de chez moi ?"})
    assert r.status_code == 200 and "pastilles" in r.text
