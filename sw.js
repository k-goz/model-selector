self.addEventListener('install',function(){self.skipWaiting();});
self.addEventListener('activate',function(event){event.waitUntil(self.clients.claim());});
self.addEventListener('notificationclick',function(event){
  event.notification.close();
  event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(function(clients){
    if(clients.length)return clients[0].focus();
    return self.clients.openWindow('/');
  }));
});
