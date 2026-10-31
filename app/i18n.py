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
    "Le ticket est lu pour en extraire les produits et les prix (par une IA quand son format n'est pas encore connu). Les numéros de carte ne sont jamais conservés.":
        "The receipt is read to extract the products and prices (by an AI when its format is not known yet). Card numbers are never kept.",
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
    "Combien coûte ma liste dans chaque enseigne ?": "How much is my list in each store?",
    "Combien coûte mon panier habituel dans chaque enseigne ?": "How much is my usual basket in each store?",
    "Comparer mon panier": "Compare my basket", "Combien coûte mon panier habituel ?": "How much is my usual basket?",
    "Combien coûte ma liste ?": "How much is my list?",
    "Ajoutez des articles à votre liste, ou quelques tickets, pour comparer un panier.":
        "Add items to your list, or a few receipts, to compare a basket.",
    "Vos {n} produits les plus achetés, comptés autant de fois que vous les achetez.":
        "Your {n} most bought products, each counted as often as you buy it.",
    "Le mieux pour vos courses": "Best for your shopping", "Le mieux pour cette liste": "Best for this list",
    "Environ {pct} % moins cher que ce que vous payez aujourd'hui, sur {n} produits comparés.":
        "About {pct}% cheaper than what you pay today, across {n} products compared.",
    "Vous payez déjà parmi les meilleurs prix relevés pour ces produits.":
        "You already pay some of the best prices found for these products.",
    "{pct} % moins cher": "{pct}% cheaper", "{pct} % plus cher": "{pct}% more expensive", "même prix": "same price",
    "Où faire mes courses habituelles ?": "Where should I do my usual shopping?",
    "Les {n} articles de votre liste.": "The {n} items on your list.",
    "Vos propres prix d'abord, sinon les prix relevés dans le quartier.": "Your own prices first, otherwise prices reported nearby.",
    "Panier malin": "Smart basket",
    "Calcul en cours : on cherche chaque article dans les magasins du quartier…": "Calculating: looking for each item in nearby stores…",
    "En prenant chaque article là où il est le moins cher ({n} / {total} articles trouvés).":
        "Buying each item where it is cheapest ({n} / {total} items found).",
    "{n} / {total} articles trouvés": "{n} / {total} items found",
    "vos achats · {date}": "your purchases · {date}", "pas trouvé dans cette enseigne": "not found in this store",
    "Estimation : les formats peuvent différer d'une enseigne à l'autre (ouvrez une enseigne pour voir le produit retenu). Le pourcentage compare les mêmes produits à ce que vous payez aujourd'hui.":
        "Estimate: sizes may differ between stores (open a store to see the product used). The percentage compares the same products with what you pay today.",
    "Touchez un prix pour voir le ticket.": "Tap a price to see the receipt.",
    "Plusieurs morceaux d'un même ticket : seulement des photos.": "Several parts of one receipt: photos only.",
    "Modifier": "Edit", "Adresse du magasin inconnue": "Store address unknown", "L'indiquer": "Add it",
    "Enregistrer l'adresse": "Save the address",
    "Adresse": "Address", "12 rue de Flandre": "12 rue de Flandre", "Code postal": "Postcode", "Ville": "City",
    "Ticket trop long ? Plusieurs photos": "Receipt too long? Several photos", "Ticket long": "Long receipt",
    "Photographiez le ticket en plusieurs fois, du haut vers le bas, en laissant une ou deux lignes en commun entre deux photos.":
        "Photograph the receipt in several parts, from top to bottom, keeping one or two lines in common between photos.",
    "Choisir dans la galerie": "Choose from gallery",
    "Prendre la première photo (le haut)": "Take the first photo (the top)",
    "Prendre la photo suivante": "Take the next photo", "Lire le ticket ({n} photos)": "Read the receipt ({n} photos)",
    "Voir le ticket du {date} chez {enseigne}": "See the receipt from {date} at {enseigne}",
    "Essayez": "Try", "Autour de vous": "Near you", "promo": "deal",
    "Prix relevés dans les magasins du quartier ces 90 derniers jours.": "Prices reported in nearby stores over the last 90 days.",
    "Magasins à moins de {km} km de votre position, prix des 90 derniers jours.":
        "Stores within {km} km of your location, prices from the last 90 days.",
    "Magasins à moins de {km} km de là où vous faites vos courses, prix des 90 derniers jours.":
        "Stores within {km} km of where you shop, prices from the last 90 days.",
    "Magasins autour de {ville} (zone par défaut) : elle s'adapte toute seule à vos magasins dès votre premier ticket.":
        "Stores around {ville} (default area): it adapts to your stores on its own from your first receipt.",
    "Autour de moi": "Near me",
    "Le bon nom du produit (précisez bio, marque, format si besoin)":
        "The right product name (add organic, brand, size if needed)",
    "Corriger": "Fix",
    "Cochez les cases encadrées en rouge pour créer votre compte.":
        "Tick the boxes outlined in red to create your account.",
    "L'e-mail peut arriver dans les spams : pensez à y regarder, et touchez « Ce n'est pas un spam ».":
        "The e-mail may land in spam: check there, and tap “Not spam”.", "pièce": "item",
    "Prix réellement payés sur vos tickets, remises déduites, ramenés à la pièce, au kilo ou au litre : un lot de 2 avocats se compare à un avocat seul.":
        "Prices actually paid on your receipts, discounts included, per item, per kilo or per litre: a pack of 2 avocados compares with a single one.", "Bio": "Organic",
    "Touchez un prix pour voir le ticket. Pas le même produit ? Touchez son nom sur le ticket pour le corriger.":
        "Tap a price to see the receipt. Not the same product? Tap its name on the receipt to fix it.",
    "Vos lignes « {libelle} » de cette enseigne prennent ce nom tout de suite, et vos prochains tickets aussi. Pour les autres, c'est un avis : il s'applique dès qu'il est le mieux soutenu.":
        "Your “{libelle}” lines from this chain take this name right away, and your future receipts too. For others it counts as a vote: it applies once it is the best supported.",
    "Exemple réel": "Real example",
    "Ce que FairBasket a trouvé dans les tickets d'un testeur": "What FairBasket found in a tester's receipts",
    "Lait bio Lactel 1 L": "Lactel organic milk 1 L", "même marque, même bouteille": "same brand, same bottle",
    "33 % plus cher pour exactement le même produit.": "33% more for exactly the same product.",
    "Chips salées 150 g": "Salted crisps 150 g", "même format": "same size", "27 % plus cher.": "27% more.",
    "Pavé de saumon bio": "Organic salmon fillet", "bio des deux côtés": "organic on both sides",
    "Ici, c'est l'autre enseigne la moins chère.": "Here, the other chain is cheaper.",
    "Le moins cher n'est pas toujours le même magasin : FairBasket compare produit par produit.":
        "The cheapest isn't always the same store: FairBasket compares product by product.",
    "95 tickets ajoutés en quelques minutes grâce aux PDF de sa carte de fidélité.":
        "95 receipts added in minutes thanks to the PDFs from their loyalty card.",
    "Ajouter mon premier ticket": "Add my first receipt",
    "Astuce : avec une carte de fidélité, téléchargez vos tickets en PDF depuis le site de l'enseigne et ajoutez-les tous d'un coup.":
        "Tip: with a loyalty card, download your receipts as PDFs from the store's website and add them all at once.",
    "Un souci ? Une idée ?": "A problem? An idea?", "Merci !": "Thank you!", "Continuer": "Continue",
    "Votre message est bien arrivé. Il aide à améliorer FairBasket pour tout le monde.":
        "Your message has arrived. It helps make FairBasket better for everyone.",
    "Dites-nous ce qui bloque, ce qui manque ou ce qui vous plaît. Quelques mots suffisent.":
        "Tell us what's not working, what's missing or what you like. A few words are enough.",
    "Votre message": "Your message", "Écrivez quelques mots.": "Write a few words.",
    "Votre e-mail, pour vous répondre (facultatif)": "Your e-mail, so we can reply (optional)",
    "Ça ne marche toujours pas ? Dites-le-nous": "Still not working? Let us know",
    "Un problème avec ce ticket ? Dites-le-nous": "A problem with this receipt? Let us know",
    "Vous n'arrivez pas à vous connecter ? Dites-le-nous": "Can't sign in? Let us know",
    "Installer l'application": "Install the app", "Installer FairBasket sur votre téléphone": "Install FairBasket on your phone",
    "Touchez le bouton Partager, puis « Sur l'écran d'accueil ».": "Tap the Share button, then “Add to Home Screen”.",
    "Une icône sur l'écran d'accueil, comme une vraie application.": "An icon on your home screen, like a real app.",
    "Installer": "Install", "Plus tard": "Later", "Revenir à mes magasins": "Back to my stores",
    "Chargement des prix autour de vous… Revenez dans une minute.": "Loading prices near you… Come back in a minute.",
    "Pas encore de prix relevé près de vous pour « {q} ».": "No price reported near you yet for “{q}”.",
    "Votre téléphone ne donne pas sa position.": "Your phone doesn't share its location.",
    "Position refusée : les prix restent ceux autour de vos magasins.":
        "Location denied: prices stay those around your stores.",
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
    "Exporter mes {n} tickets (CSV)": "Export my {n} receipts (CSV)", "Supprimer mon compte et toutes mes données": "Delete my account and all my data",
    "Vos tickets, leurs fichiers et votre compte seront supprimés définitivement. Les prix déjà partagés de façon anonyme restent, sans lien avec vous.":
        "Your receipts, their files and your account will be permanently deleted. Prices already shared anonymously remain, with no link to you.",
    "Tapez SUPPRIMER pour confirmer": "Type SUPPRIMER to confirm", "Tout supprimer": "Delete everything",
    "Se déconnecter": "Log out", "Mentions légales": "Legal notice", "Confidentialité": "Privacy", "Conditions": "Terms",
    # bilan d'un ticket
    "Ce ticket comparé à vos achats": "This receipt compared with your purchases",
    "Premiers achats de ces produits : la comparaison apparaîtra dès votre prochain ticket.":
        "First purchase of these products: the comparison will appear with your next receipt.",
    "économisés par rapport à vos derniers achats": "saved compared with your last purchases",
    "de plus que vos derniers achats": "more than your last purchases", "comme vos derniers achats": "same as your last purchases",
    "Sur {n} produit(s) déjà achetés, au prix à la pièce, au kilo ou au litre.":
        "On {n} product(s) bought before, per item, kilo or litre.",
    "moins cher(s)": "cheaper", "plus cher(s)": "more expensive",
    "avant : {prix} chez {enseigne} le {date}": "before: {prix} at {enseigne} on {date}",
    "Ailleurs, vous auriez payé {montant} de moins": "Elsewhere, you would have paid {montant} less",
    "{produit} : {prix} chez {enseigne}": "{produit}: {prix} at {enseigne}",
    "Nouveaux produits : {n}, comparés au prochain achat.": "New products: {n}, compared next time.",
    # assistant
    "Où faites-vous vos courses ?": "Where do you shop?",
    "Je trouve les magasins à côté de chez vous, puis je compare leurs prix.": "I find the stores near you, then compare their prices.",
    "Ensuite, je réponds à : « {question} »": "Then I'll answer: “{question}”",
    "Je n'ai pas trouvé ce lieu : essayez un code postal.": "I couldn't find that place: try a postcode.",
    "Magasins autour de {lieu}": "Stores around {lieu}", "vos magasins habituels": "your usual stores", "changer": "change",
    "Code postal ou ville": "Postcode or town", "Code postal ou ville : 75019, Lyon 3…": "Postcode or town: 75019, Lyon 3…",
    "OK": "OK",
    "Gardé sur votre compte à environ 1 km près, jamais votre adresse exacte. Modifiable dans Profil.":
        "Kept on your account to within about 1 km, never your exact address. Change it in Profile.",
    "Mon quartier": "My neighbourhood", "Autour des magasins de vos tickets": "Around the stores on your receipts",
    "Pas encore indiqué : les prix sont ceux de {ville}.": "Not set yet: prices are those of {ville}.",
    "Les magasins à côté, que l'app compare pour vous :": "Stores nearby, which the app compares for you:",
    "Indiquer ou changer mon quartier": "Set or change my neighbourhood", "Indiquer mon quartier": "Set my neighbourhood",
    "Magasins à moins de {km} km de votre quartier, prix des 90 derniers jours.": "Stores within {km} km of your neighbourhood, prices from the last 90 days.",
    "meilleur choix": "best choice", "tout près": "very close", "le plus proche": "nearest", "prix en ligne": "online price",
    "vous y allez déjà": "you already shop there", "Itinéraire": "Directions", "Voir en ligne": "See online",
    "Bon à savoir": "Good to know",
    "Le meilleur choix : {produit} à {prix} chez {enseigne}{ou}.": "Best choice: {produit} at {prix} at {enseigne}{ou}.",
    "{n} autre(s) choix ci-dessous.": "{n} other choice(s) below.",
    "Vous le payez d'habitude {prix} chez {enseigne} : chez {meilleur}, vous économisez {gain} ({pct} %) à chaque achat.":
        "You usually pay {prix} at {enseigne}: at {meilleur}, you save {gain} ({pct}%) each time.",
    "Dans votre liste, {articles} y sont aussi au meilleur prix : une seule course pour tout.":
        "On your list, {articles} are also cheapest there: one trip for everything.",
    "Vous faites déjà vos courses chez {enseigne} : ajoutez-le à votre prochain passage.":
        "You already shop at {enseigne}: add it to your next trip.",
    "C'est à environ {minutes} minutes à pied de chez vous.": "It's about a {minutes}-minute walk from you.",
    "Personne n'a encore de prix pour « {q} » autour de vous.": "Nobody has a price for “{q}” near you yet.",
    "Où trouver {q} moins cher près de chez moi ?": "Where can I find cheaper {q} near me?",
    "Chercher les prix en ligne": "Search prices online",
    "Dans votre liste, l'app vous dira où c'est le moins cher dès que vous ou quelqu'un d'autre l'achetez.":
        "On your list, the app will tell you where it's cheapest as soon as you or someone else buys it.",
    "Demandez-moi": "Ask me", "Demander": "Ask", "Où faire mes courses": "Where to shop", "Votre question": "Your question",
    "Demandez-moi : où acheter moins cher…": "Ask me: where to buy cheaper…",
    "Où acheter moins cher, ce que vous dépensez, votre liste : posez votre question comme vous la diriez.":
        "Where to buy cheaper, what you spend, your list: ask the way you would say it.",
    "Je cherche… cela peut prendre quelques secondes.": "Searching… this can take a few seconds.",
    "Où trouver des pastilles lave-vaisselle moins chères ?": "Where can I find cheaper dishwasher tablets?",
    "Combien j'ai dépensé en fromage ce mois-ci ?": "How much did I spend on cheese this month?",
    "Ajoute du lait à ma liste": "Add milk to my list",
    "Voir les {n} prix trouvés": "See the {n} prices found", "vos tickets": "your receipts",
    "autres utilisateurs": "other users", "Sources :": "Sources:", "Ajouter à ma liste": "Add to my list",
    "Utile ?": "Helpful?", "Utile": "Helpful", "Pas utile": "Not helpful", "Merci pour votre avis.": "Thanks for your feedback.",
    "Questions avancées restantes ce mois-ci : {n}. Les questions simples sont illimitées.":
        "Advanced questions left this month: {n}. Simple questions are unlimited.",
    "C'est noté : « {produit} » est dans votre liste.": "Done: “{produit}” is on your list.",
    "ce mois-ci": "this month", "sur les 12 derniers mois": "over the last 12 months",
    "Rayon {rayon} : {total} {periode}.": "{rayon}: {total} {periode}.",
    "Je ne trouve pas « {produit} » dans vos tickets {periode}.": "I can't find “{produit}” in your receipts {periode}.",
    "« {produit} » : {total} {periode}, en {n} achat(s).": "“{produit}”: {total} {periode}, in {n} purchase(s).",
    "Vous avez dépensé {total} {periode}, en {n} ticket(s).": "You spent {total} {periode}, over {n} receipt(s).",
    "({signe}{evolution} % par rapport à la période précédente)": "({signe}{evolution}% compared with the previous period)",
    "Je ne connais pas encore de prix pour « {produit} » près de chez vous. Ajoutez-le à votre liste : dès que vous ou quelqu'un d'autre l'achetez, l'app vous dira où c'est le moins cher.":
        "I don't know any price for “{produit}” near you yet. Add it to your list: as soon as you or someone else buys it, the app will tell you where it's cheapest.",
    "Dans vos tickets, le moins cher : {produit} à {prix} chez {enseigne} (le {date}).":
        "In your receipts, the cheapest: {produit} at {prix} at {enseigne} (on {date}).",
    "D'autres utilisateurs l'ont payé {prix} chez {enseigne} ({magasin}).": "Other users paid {prix} at {enseigne} ({magasin}).",
    "Autour de chez vous (Open Prices, moins de {km} km) : {produit} à {prix} chez {magasin}, relevé le {date}.":
        "Near you (Open Prices, within {km} km): {produit} at {prix} at {magasin}, recorded on {date}.",
    "Pour votre panier habituel, ouvrez « Où faire mes courses » : l'app y compare ce que vous achetez d'habitude dans chaque enseigne autour de chez vous.":
        "For your usual basket, open “Where to shop”: the app compares what you usually buy in each store near you.",
    "Désolé, je n'ai pas pu répondre. Réessayez dans un instant.": "Sorry, I couldn't answer. Please try again in a moment.",
    "Je n'ai pas compris. Essayez par exemple : « Où trouver des œufs bio moins chers ? », « Combien j'ai dépensé en fromage ce mois-ci ? » ou « Ajoute du lait à ma liste ».":
        "I didn't understand. Try for example: “Where can I find cheaper organic eggs?”, “How much did I spend on cheese this month?” or “Add milk to my list”.",
    # rayon
    "Touchez un rayon pour voir ce que vous y achetez. Évolution par rapport à {mois}.":
        "Tap an aisle to see what you buy there. Change compared with {mois}.",
    "Touchez un rayon pour voir ce que vous y achetez. Évolution par rapport aux 12 mois précédents.":
        "Tap an aisle to see what you buy there. Change compared with the previous 12 months.",
    "{montant} en {mois}": "{montant} in {mois}", "{montant} sur 12 mois": "{montant} over 12 months",
    "Ce que vous y achetez": "What you buy there",
    "Un produit n'est pas dans le bon rayon ? Touchez-le, puis son nom sur le ticket pour changer son rayon.":
        "A product in the wrong aisle? Tap it, then its name on the receipt to change its aisle.",
    "Rien dans ce rayon sur les 12 derniers mois.": "Nothing in this aisle over the last 12 months.",
    "Rayon": "Aisle", "Changer le rayon": "Change aisle",
    # rayons et enseignes particulieres (valeurs stockees en francais)
    "Fruits et légumes": "Fruit and vegetables", "Viandes et poissons": "Meat and fish",
    "Produits laitiers et œufs": "Dairy and eggs", "Fromages": "Cheese", "Boulangerie": "Bakery",
    "Épicerie salée": "Savoury groceries", "Épicerie sucrée": "Sweet groceries", "Boissons": "Drinks",
    "Surgelés": "Frozen", "Hygiène et beauté": "Health and beauty", "Entretien et maison": "Household", "Autre": "Other",
    "Inconnue": "Unknown", "Marché": "Market", "Commerce": "Shop",
    # code-barres
    "Code-barres": "Barcode", "Produit reconnu": "Product recognised",
    "Déjà connu : les prochains tickets « {libelle} » de {enseigne} le reconnaîtront tout seuls. Pas le bon ? Scannez à nouveau.":
        "Already known: the next « {libelle} » receipts from {enseigne} will recognise it on their own. Wrong one? Scan again.",
    "Ce code-barres ne semble pas complet.": "This barcode doesn't look complete.",
    "Vérifiez les chiffres sous les barres (8 ou 13 en général).": "Check the digits under the bars (usually 8 or 13).",
    "Scanner le code-barres du paquet": "Scan the barcode on the pack",
    "Visez les barres, à 10–15 cm. Ça se fait tout seul.": "Aim at the bars, 10–15 cm away. It happens on its own.",
    "Ou touchez le bon produit": "Or tap the right product",
    "Ou tapez les chiffres : 3350030224462": "Or type the digits: 3350030224462",
    "Une seule fois par produit : ensuite FairBasket connaît l'article exact (marque, format, vrai prix au kilo) et le compare au même article dans les autres magasins.":
        "Only once per product: FairBasket then knows the exact item (brand, size, true price per kilo) and compares it with the same item in other stores.",
    "Fiches produits : Open Food Facts (licence ODbL).": "Product data: Open Food Facts (ODbL licence).",
    "Scanner le code-barres (article exact)": "Scan the barcode (exact item)", "Changer le code-barres": "Change the barcode",
    "Le même : {prix} chez {magasin}": "Same item: {prix} at {magasin}",
    # sante
    "brut ou peu transformé": "unprocessed or minimally processed", "ingrédient culinaire": "culinary ingredient",
    "transformé": "processed", "ultra-transformé": "ultra-processed", "Additifs : {liste}": "Additives: {liste}",
    "Sans additif": "No additives", "Label Rouge": "Label Rouge", "Commerce équitable": "Fair trade",
    "Pêche durable MSC": "MSC sustainable fishing", "Plein air": "Free range", "Végétarien": "Vegetarian",
    "Sans huile de palme": "No palm oil", "Sans sucres ajoutés": "No added sugar", "Origine France": "French origin",
    "Fabriqué en France": "Made in France", "chez {ou}": "at {ou}", "{ecart}/{unite} de moins": "{ecart}/{unite} less",
    "Mieux noté :": "Better rated:", "Mieux noté dans le même rayon": "Better rated in the same aisle",
    "Nutri-Score : {pct} % en A ou B, sur {montant} d'articles scannés.":
        "Nutri-Score: {pct} % A or B, out of {montant} of scanned items.",
    "Notes officielles Nutri-Score et classement NOVA, d'après Open Food Facts. À vous de choisir.":
        "Official Nutri-Score ratings and NOVA groups, from Open Food Facts. Your choice.",
    "Une alternative plus saine aux céréales ?": "A healthier alternative to cereals?",
    "« {nom} » a le Nutri-Score {note} : je n'ai rien trouvé de mieux noté dans le même rayon.":
        "« {nom} » has Nutri-Score {note}: I found nothing better rated in the same aisle.",
    "Je n'ai pas trouvé de produit mieux noté pour « {produit} ». Scannez le code-barres du vôtre depuis un ticket : je comparerai dans son rayon exact.":
        "I found no better-rated product for « {produit} ». Scan your product's barcode from a receipt: I'll compare within its exact aisle.",
    " à {prix} chez {ou}": " at {prix} from {ou}",
    "Votre « {nom} » a le Nutri-Score {note}. Mieux noté dans le même rayon : {mieux}, Nutri-Score {note_mieux}{prix}.":
        "Your « {nom} » has Nutri-Score {note}. Better rated in the same aisle: {mieux}, Nutri-Score {note_mieux}{prix}.",
    "Le mieux noté pour « {produit} » : {mieux}, Nutri-Score {note_mieux}{prix}.":
        "Best rated for « {produit} »: {mieux}, Nutri-Score {note_mieux}{prix}.",
    "Merci ! Ça aide tous ceux qui achètent cet article.": "Thanks! This helps everyone who buys this item.",
    "Une petite vérification, si vous voulez": "A quick check, if you like",
    "« {libelle} », c'est bien :": "“{libelle}” is it really:",
    "Oui": "Yes",
    "Non, corriger": "No, fix it",
    "Un autre code-barres est déjà retenu pour « {libelle} ». Votre scan compte comme un avis : il l'emportera si quelqu'un d'autre le confirme.":
        "Another barcode is already kept for “{libelle}”. Your scan counts as a vote: it will win if someone else confirms it.",
    "Vos corrections ont servi à {n} personnes": "Your fixes have helped {n} people",
    "Vos corrections ont servi à une autre personne": "Your fixes have helped one other person",
    "Merci pour vos {n} corrections": "Thanks for your {n} fixes",
    "Merci pour votre correction": "Thanks for your fix",
    "Les noms de produits que vous corrigez, confirmez ou scannez aident tous ceux qui achètent les mêmes articles. Votre nom n'est jamais montré.":
        "Product names you fix, confirm or scan help everyone who buys the same items. Your name is never shown.",
    "Produit type : {type}": "Product type: {type}",
    "Articles semblables, même produit type : chaque ligne dit lequel.":
        "Similar items, same product type: each line says which one.",
    "{produit} : {prix} chez {enseigne} ({autre})": "{produit}: {prix} at {enseigne} ({autre})",
}
