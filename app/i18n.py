"""Traduction de l'interface. Le texte francais sert de cle ; l'anglais est dans EN.

tests/test_i18n.py verifie que chaque texte des gabarits a sa traduction.
"""

from datetime import date

LANGUES = ("fr", "en")
MOIS = {
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}



def traducteur(lang: str):
    table = EN if lang == "en" else {}

    def _(texte: str, **valeurs) -> str:
        texte = table.get(texte, texte)
        if "n" in valeurs and "(s)" in texte:
            # « {n} achat(s) » : « 1 achat », « 2 achats »
            texte = texte.replace("(s)", "s" if valeurs["n"] != 1 else "")
        return texte.format(**valeurs) if valeurs else texte

    return _


def nom_mois(lang: str):
    def mois(d: date, avec_annee: bool = True, court: bool = False) -> str:
        nom = MOIS[lang if lang in MOIS else "fr"][d.month - 1]
        if court:
            nom = nom[:1].upper()
        return f"{nom} {d.year}" if avec_annee and not court else nom

    return mois


def langue_demandee(cookie: str, accept_language: str) -> str:
    if cookie in LANGUES:
        return cookie
    return "en" if (accept_language or "").lower().startswith("en") else "fr"


EN = {
    # navigation et commun
    "Accueil": "Home", "Comparer": "Compare", "Liste": "List", "Profil": "Profile",
    "Navigation principale": "Main navigation", "Ajouter un ticket": "Add a receipt", "Retour": "Back",
    "Fermer": "Close", "Ticket": "Receipt", "Tickets": "Receipts", "Enregistrer": "Save",
    "date inconnue": "unknown date", "Magasin inconnu": "Unknown store",
    # inscription et connexion
    "Inscription": "Sign up", "Connexion": "Log in", "Payez le juste prix de votre panier.": "Pay the fair price for your basket.",
    "Ajoutez vos tickets de caisse : FairBasket analyse vos dépenses et vous dit où acheter moins cher.":
        "Add your till receipts: FairBasket analyses your spending and tells you where to buy for less.",
    "Votre compte et toutes vos données ont été supprimés.": "Your account and all your data have been deleted.",
    "Prénom": "First name", "E-mail": "Email", "J'ai 18 ans ou plus.": "I am 18 or older.",
    "J'accepte les {cgu} et la {confidentialite}.": "I accept the {cgu} and the {confidentialite}.",
    "conditions d'utilisation": "terms of use", "politique de confidentialité": "privacy policy",
    "J'accepte que mes tickets soient lus par une IA (Claude, d'Anthropic) pour en extraire les produits et les prix.":
        "I agree that my receipts are read by an AI (Claude, by Anthropic) to extract the products and prices.",
    "Facultatif.": "Optional.",
    "Partager mes prix de façon anonyme pour aider les autres utilisateurs : produit, magasin, prix et date, jamais mon identité.":
        "Share my prices anonymously to help other users: product, store, price and date, never my identity.",
    "Recevoir mon lien de connexion": "Get my login link",
    "Pas de mot de passe : un lien de connexion arrive par e-mail.": "No password: a login link arrives by email.",
    "Déjà inscrit ?": "Already signed up?", "Se connecter": "Log in", "S'inscrire": "Sign up",
    "Pas encore de compte ?": "No account yet?",
    "Indiquez votre adresse : nous vous envoyons un lien de connexion.": "Enter your email: we will send you a login link.",
    "Recevoir mon lien": "Get my link", "Vérifiez vos e-mails": "Check your email",
    "Votre compte est créé. Un lien de connexion vient d'être envoyé à {email}. Il est valable 15 minutes et ne sert qu'une fois.":
        "Your account is created. A login link has just been sent to {email}. It is valid for 15 minutes and works once.",
    "Si un compte actif existe pour {email}, un lien de connexion vient d'y être envoyé. Il est valable 15 minutes et ne sert qu'une fois.":
        "If an active account exists for {email}, a login link has just been sent to it. It is valid for 15 minutes and works once.",
    "Renvoyer un lien": "Send a new link", "Rien reçu ? Regardez dans les spams, ou changez d'adresse.":
        "Nothing received? Check your spam folder, or use another address.",
    "Changer d'adresse": "Use another address", "Liste d'attente": "Waiting list",
    "Vous êtes sur la liste d'attente": "You are on the waiting list",
    "Merci {prenom} ! FairBasket ouvre par petits groupes pendant la bêta. Vous recevrez un e-mail dès que votre accès est prêt.":
        "Thank you {prenom}! FairBasket opens in small groups during the beta. You will get an email as soon as your access is ready.",
    "En attendant, gardez vos tickets de caisse : vous pourrez les ajouter dès l'ouverture.":
        "Meanwhile, keep your till receipts: you can add them as soon as you are in.",
    "Lien expiré": "Link expired", "Ce lien ne fonctionne plus": "This link no longer works",
    "Un lien de connexion est valable 15 minutes et ne sert qu'une seule fois. Demandez-en un nouveau.":
        "A login link is valid for 15 minutes and works only once. Ask for a new one.",
    "Recevoir un nouveau lien": "Get a new link",
    "Indiquez votre prénom (50 caractères maximum).": "Enter your first name (50 characters maximum).",
    "Indiquez une adresse e-mail valide.": "Enter a valid email address.",
    "Les trois premières cases sont nécessaires pour créer un compte.": "The first three boxes are required to create an account.",
    # presentation
    "Présentation": "Introduction", "Passer": "Skip", "Suivant": "Next", "Ajouter mon premier ticket": "Add my first receipt",
    "Ajoutez vos tickets": "Add your receipts",
    "Prenez le ticket en photo à la sortie du magasin, ou déposez le PDF reçu par e-mail. Toutes les enseignes fonctionnent.":
        "Take a photo of the receipt when you leave the store, or upload the PDF you got by email. Any store works.",
    "Voyez où part votre argent": "See where your money goes",
    "Dépenses par mois, par magasin, par rayon et par produit, calculées automatiquement. Rien à saisir à la main.":
        "Spending by month, store, aisle and product, calculated automatically. Nothing to type in.",
    "Payez le juste prix": "Pay the fair price",
    "FairBasket compare les prix de vos produits habituels et vous dit où faire vos courses pour payer moins cher.":
        "FairBasket compares the prices of your usual products and tells you where to shop to pay less.",
    # tableau de bord
    "Bonjour {prenom}": "Hello {prenom}", "Période": "Period", "Ce mois": "This month", "12 mois": "12 months",
    "{n} ticket(s) à vérifier": "{n} receipt(s) to check",
    "La somme des articles ne correspond pas au total.": "The items do not add up to the total.",
    "par rapport à {mois}": "compared with {mois}", "par rapport aux 12 mois précédents": "compared with the previous 12 months",
    "Pas encore de ticket. Appuyez sur + pour ajouter le premier : vos dépenses s'afficheront ici.":
        "No receipt yet. Tap + to add the first one: your spending will show here.",
    "Panier moyen": "Average basket", "Dépenses par mois": "Spending by month",
    "Dépenses des 12 derniers mois": "Spending over the last 12 months", "Par enseigne": "By store",
    "Par rayon": "By aisle", "À savoir": "Good to know", "Moins cher ailleurs": "Cheaper elsewhere",
    "{produit} : {prix} chez {enseigne}, contre {prix_habituel} chez {habituelle}.":
        "{produit}: {prix} at {enseigne}, versus {prix_habituel} at {habituelle}.",
    "Vos premiers postes": "Where most of your money goes", "{n} achat(s)": "{n} purchase(s)",
    "Derniers tickets": "Latest receipts", "à vérifier": "to check",
    "Administration · liste d'attente": "Admin · waiting list",
    # ajout et ticket
    "Tickets ce mois : {n} / {max}": "Receipts this month: {n} / {max}",
    "Ticket papier ou PDF reçu par e-mail : n'importe quelle enseigne.": "Paper receipt or PDF received by email: any store.",
    "Prendre une photo": "Take a photo", "Posez le ticket à plat, bien éclairé": "Lay the receipt flat, in good light",
    "Choisir un PDF ou une photo": "Choose a PDF or a photo", "Envoyer": "Send",
    "Le ticket est lu par une IA pour en extraire les produits et les prix. Les numéros de carte ne sont jamais conservés.":
        "The receipt is read by an AI to extract the products and prices. Card numbers are never kept.",
    "Lecture du ticket…": "Reading the receipt…",
    "Vous pouvez en sélectionner plusieurs.": "You can select several.",
    "Voir mon tableau de bord": "See my dashboard",
    "Lecture {i} / {n} : {nom}": "Reading {i} / {n}: {nom}",
    "Ajoutés : {ok} · Déjà présents : {doublons} · En échec : {echecs}":
        "Added: {ok} · Already there: {doublons} · Failed: {echecs}",
    "Lecture terminée": "Done",
    "Quelques secondes : l'IA lit le magasin, la date, chaque article et vérifie le total.":
        "A few seconds: the AI reads the store, the date, every item, and checks the total.",
    "Envoi impossible : vérifiez votre connexion et réessayez.": "Could not send: check your connection and try again.",
    "Le fichier est vide.": "The file is empty.", "Fichier trop lourd (30 Mo maximum).": "File too large (30 MB maximum).",
    "Format non pris en charge : envoyez un PDF ou une photo (JPEG, PNG).": "Unsupported format: send a PDF or a photo (JPEG, PNG).",
    "Limite de {n} tickets par mois atteinte.": "Limit of {n} receipts per month reached.",
    "Ce ticket n'a pas pu être lu. Reprenez la photo à plat, bien éclairée.": "This receipt could not be read. Take the photo again, flat and in good light.",
    "La lecture a été refusée par le modèle.": "The AI declined to read this receipt.",
    "Ticket trop long pour être lu en une fois.": "Receipt too long to be read in one go.",
    "Ce ticket était déjà enregistré.": "This receipt was already saved.",
    "Il n'a pas été ajouté une deuxième fois.": "It was not added a second time.",
    "Total vérifié : la somme des {n} articles est égale au total du ticket.": "Total checked: the {n} items add up to the receipt total.",
    "Remises": "Discounts", "Total du ticket": "Receipt total", "Somme des articles lus": "Sum of the items read",
    "Écart": "Difference", "Corrigez un montant ou ajoutez la ligne manquante pour que vos statistiques restent justes.":
        "Fix an amount or add the missing line so your figures stay accurate.",
    "Produit": "Product", "Montant": "Amount", "Ligne manquante": "Missing line",
    "Enregistrer les corrections": "Save corrections", "Magasin inconnu : indiquez-le": "Unknown store: tell us which one",
    "Changer de magasin": "Change store", "Enseigne": "Store chain", "Monoprix, Marché, Picard…": "Monoprix, Market, Picard…",
    "Magasin (facultatif)": "Store (optional)", "Crimée, marché Jean-Jaurès…": "Crimée, Jean-Jaurès market…",
    "Enregistrer le magasin": "Save store", "Note de lecture : {note}": "Reading note: {note}",
    "Supprimer ce ticket ?": "Delete this receipt?", "Supprimer ce ticket": "Delete this receipt",
    # comparer
    "Comparer les prix": "Compare prices", "Rechercher un produit": "Search for a product", "Source des prix": "Price source",
    "Mes achats": "My purchases", "Communauté": "Community", "Votre panier habituel": "Your usual basket",
    "Le moins cher le plus souvent : {enseigne}": "Cheapest most often: {enseigne}",
    "Moins cher sur {n} de vos {total} produits achetés dans plusieurs enseignes, au dernier prix payé.":
        "Cheapest for {n} of your {total} products bought in several stores, at the last price paid.",
    "le moins cher": "cheapest",
    "Aucun produit ne correspond à « {q} ».": "No product matches “{q}”.",
    "Essayez": "Try", "Autour de vous": "Near you", "promo": "deal",
    "Prix relevés dans les magasins du quartier ces 90 derniers jours.": "Prices reported in nearby stores over the last 90 days.",
    "Source : {source}, base ouverte de prix d'Open Food Facts, licence ODbL.": "Source: {source}, Open Food Facts' open price database, ODbL licence.", "Saumon, œufs, fromage…": "Salmon, eggs, cheese…",
    "Acheté seulement chez {enseigne} : pas encore de comparaison.": "Only bought at {enseigne}: nothing to compare yet.",
    "Les comparaisons apparaissent quand vous avez acheté le même produit dans au moins deux enseignes.":
        "Comparisons appear once you have bought the same product in at least two stores.",
    "Prix réellement payés sur vos tickets, à l'unité. Les produits vendus au poids ne sont pas encore comparés.":
        "Prices actually paid on your receipts, per unit. Products sold by weight are not compared yet.",
    "{n} relevé(s)": "{n} report(s)", "Les prix relevés près de chez vous": "Prices reported near you",
    "Pas encore assez de prix partagés pour vos produits. Chaque ticket partagé de façon anonyme aide tout le monde à trouver le meilleur prix.":
        "Not enough shared prices for your products yet. Every receipt shared anonymously helps everyone find the best price.",
    "Prix partagés anonymement par les utilisateurs ces 90 derniers jours (prix médian par magasin).":
        "Prices shared anonymously by users over the last 90 days (median price per store).",
    # liste
    "Ma liste": "My list", "Estimation": "Estimate", "Ajouter un article": "Add an item", "Dicter un article": "Dictate an item",
    "Ajouter": "Add", "Cocher {nom}": "Tick {nom}", "Décocher {nom}": "Untick {nom}",
    "Retirer les articles cochés": "Remove ticked items",
    "Votre liste est vide. Ajoutez un article, ou piochez dans ce que vous achetez souvent.":
        "Your list is empty. Add an item, or pick from what you often buy.",
    "Vous en achetez souvent": "You often buy", "Où aller pour payer le moins cher": "Where to go to pay the least",
    "{n} article(s)": "{n} item(s)",
    "D'après le dernier prix que vous avez payé dans chaque enseigne.": "Based on the last price you paid in each store.",
    # profil
    "Tickets lus ce mois": "Receipts read this month", "Langue": "Language", "Mes accords": "My consents",
    "Lecture des tickets par l'IA": "Receipts read by AI",
    "Nécessaire pour ajouter des tickets. Accepté le {date}.": "Required to add receipts. Accepted on {date}.",
    "Partager mes prix anonymement": "Share my prices anonymously",
    "Produit, magasin, prix et jour. Jamais votre identité.": "Product, store, price and day. Never your identity.",
    "Activé le {date}.": "Turned on {date}.", "Mes données": "My data",
    "Exporter mes {n} tickets (CSV)": "Export my {n} receipts (CSV)", "Supprimer toutes mes données": "Delete all my data",
    "Vos tickets, leurs fichiers et votre compte seront supprimés définitivement. Les prix déjà partagés de façon anonyme restent, sans lien avec vous.":
        "Your receipts, their files and your account will be permanently deleted. Prices already shared anonymously remain, with no link to you.",
    "Tapez SUPPRIMER pour confirmer": "Type SUPPRIMER to confirm", "Tout supprimer": "Delete everything",
    "Se déconnecter": "Log out", "Mentions légales": "Legal notice", "Confidentialité": "Privacy", "Conditions": "Terms",
    # rayons et enseignes particulieres (valeurs stockees en francais)
    "Fruits et légumes": "Fruit and vegetables", "Viandes et poissons": "Meat and fish",
    "Produits laitiers et œufs": "Dairy and eggs", "Fromages": "Cheese", "Boulangerie": "Bakery",
    "Épicerie salée": "Savoury groceries", "Épicerie sucrée": "Sweet groceries", "Boissons": "Drinks",
    "Surgelés": "Frozen", "Hygiène et beauté": "Health and beauty", "Entretien et maison": "Household", "Autre": "Other",
    "Inconnue": "Unknown", "Marché": "Market", "Commerce": "Shop",
}
