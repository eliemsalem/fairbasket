// FairBasket : rend le site installable comme une application.
// Rien n'est mis en cache (les pages sont personnelles) ; hors connexion, un message clair au lieu d'une erreur.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(() => new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>FairBasket</title><body style="font-family:system-ui;padding:32px;text-align:center">' +
    '<h1>FairBasket</h1><p>Pas de connexion internet. / No internet connection.</p>' +
    '<button onclick="location.reload()" style="padding:12px 20px;font:inherit">Réessayer / Retry</button>',
    {headers: {'Content-Type': 'text/html; charset=utf-8'}})));
});
