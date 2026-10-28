// FairBasket : rend le site installable comme une application.
// Rien n'est mis en cache (les pages sont personnelles). Hors connexion, ou pendant une mise a jour du serveur
// (Render repond alors 502/503 pendant une a deux minutes), un message clair au lieu d'une page d'erreur ;
// une page simplement consultee se recharge toute seule des que le serveur est revenu.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

const INDISPONIBLE = [502, 503, 504];

function page(titre, texte, recharger) {
  const script = recharger
    ? '<script>setTimeout(function () { location.reload(); }, 5000);</script>' : '';
  return new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>FairBasket</title><body style="font-family:system-ui;padding:32px;text-align:center;' +
    'background:#fff;color:#111"><h1>FairBasket</h1><p><strong>' + titre + '</strong></p><p>' + texte + '</p>' +
    '<button onclick="location.reload()" style="padding:12px 20px;font:inherit">Réessayer / Retry</button>' + script,
    {status: 503, headers: {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'}});
}

self.addEventListener('fetch', (e) => {
  if (e.request.mode !== 'navigate') return;
  const consultation = e.request.method === 'GET';  // un envoi (ticket, formulaire) n'est jamais renvoye seul
  const maj = consultation
    ? page('Mise à jour en cours / Updating', 'L’application revient dans un instant, la page se recharge toute seule. / Back in a moment, this page reloads by itself.', true)
    : page('Mise à jour en cours / Updating', 'Votre envoi n’a pas pu partir. Attendez une minute puis renvoyez-le. / Your submission could not be sent. Wait a minute, then send it again.', false);
  e.respondWith(fetch(e.request).then((rep) => (INDISPONIBLE.includes(rep.status) ? maj : rep)).catch(() => (
    navigator.onLine === false
      ? page('Pas de connexion internet / No internet connection', 'Vérifiez votre connexion. / Check your connection.', false)
      : maj)));
});
