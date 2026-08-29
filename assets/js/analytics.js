(function(global){
'use strict';
var allowed=['catalog_loaded','search_used','filter_used','compare_created','calculator_completed','code_copied','share_created','provider_clicked'];
function track(name,properties){
if(allowed.indexOf(name)===-1)return false;
var event={name:name,at:new Date().toISOString(),properties:properties||{}};
try{var queue=JSON.parse(sessionStorage.getItem('ms_metrics')||'[]');queue.push(event);sessionStorage.setItem('ms_metrics',JSON.stringify(queue.slice(-100)));}catch(error){}
global.dispatchEvent(new CustomEvent('model-selector:metric',{detail:event}));
return true;
}
global.ModelSelectorAnalytics={track:track,allowed:allowed.slice()};
})(window);
