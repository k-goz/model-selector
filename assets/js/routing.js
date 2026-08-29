(function(global){
'use strict';
var VERSION=2;
function encode(state){return '#v'+VERSION+'='+encodeURIComponent(JSON.stringify(state));}
function decode(hash){
var raw=String(hash||'').replace(/^#/,''),prefix='v'+VERSION+'=';
if(raw.indexOf(prefix)===0)raw=raw.slice(prefix.length);
try{return JSON.parse(decodeURIComponent(raw));}catch(error){return null;}
}
function replace(state){history.replaceState(null,'',location.pathname+location.search+encode(state));}
function languageUrl(locale,state){return (locale==='en'?'/en/':'/')+encode(state);}
global.ModelSelectorRouting={version:VERSION,encode:encode,decode:decode,replace:replace,languageUrl:languageUrl};
})(window);
