(function(global){
'use strict';
var allowed=['catalog_loaded','search_used','filter_used','compare_created','calculator_completed','code_copied','share_created','provider_clicked','price_subscription_created','price_subscription_removed','price_alert_delivered','web_vital'];
function track(name,properties){
if(allowed.indexOf(name)===-1)return false;
var event={name:name,at:new Date().toISOString(),properties:properties||{}};
try{var queue=JSON.parse(sessionStorage.getItem('ms_metrics')||'[]');queue.push(event);sessionStorage.setItem('ms_metrics',JSON.stringify(queue.slice(-100)));}catch(error){}
global.dispatchEvent(new CustomEvent('model-selector:metric',{detail:event}));
return true;
}
global.ModelSelectorAnalytics={track:track,allowed:allowed.slice()};
function observeVital(type,handler){
try{new PerformanceObserver(function(list){list.getEntries().forEach(handler);}).observe({type:type,buffered:true});}catch(error){}
}
observeVital('largest-contentful-paint',function(entry){track('web_vital',{name:'LCP',value:Math.round(entry.startTime)});});
var cls=0;observeVital('layout-shift',function(entry){if(!entry.hadRecentInput){cls+=entry.value;track('web_vital',{name:'CLS',value:Number(cls.toFixed(4))});}});
observeVital('event',function(entry){if(entry.duration>=40)track('web_vital',{name:'INP',value:Math.round(entry.duration)});});
})(window);
