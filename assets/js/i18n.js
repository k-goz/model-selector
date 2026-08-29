(function(global){
'use strict';
var dictionaries={
zh:{
'catalog.count':'显示 {count} / {total} 个模型','pagination.first':'首页','pagination.prev':'上一页',
'pagination.next':'下一页','pagination.last':'末页','pagination.summary':'第 {page} / {pages} 页 (共 {count} 个)',
'catalog.context':'上下文: {value}','catalog.integration':'点击查看接入代码','catalog.favorite':'收藏','catalog.compare':'对比',
'catalog.load_error':'模型数据加载失败，请稍后重试或直接查看 models_data.json。','share.copied':'分享链接已复制',
'trust.source':'来源','trust.updated':'采集于 {value}','trust.confidence.high':'高可信','trust.confidence.medium':'中可信','trust.confidence.low':'低可信','trust.confidence.unknown':'可信度未知',
'price.free':'免费','price.free_tier':'有免费额度 · 价格待确认','price.non_token':'非 Token 计费 · 待确认',
'price.unavailable':'已下线','price.retiring':'即将下线','price.unknown':'价格待确认'
},
en:{
'catalog.count':'Showing {count} / {total} models','pagination.first':'First','pagination.prev':'Prev',
'pagination.next':'Next','pagination.last':'Last','pagination.summary':'Page {page} / {pages} ({count} models)',
'catalog.context':'Context: {value}','catalog.integration':'Click to view integration code','catalog.favorite':'Favorite','catalog.compare':'Compare',
'catalog.load_error':'Model data failed to load. Retry later or open models_data.json directly.','share.copied':'Share link copied',
'trust.source':'Source','trust.updated':'Collected {value}','trust.confidence.high':'High confidence','trust.confidence.medium':'Medium confidence','trust.confidence.low':'Low confidence','trust.confidence.unknown':'Unknown confidence',
'price.free':'Free','price.free_tier':'Free tier · price unverified','price.non_token':'Non-token billing · unverified',
'price.unavailable':'Unavailable','price.retiring':'Retiring','price.unknown':'Price unverified'
}};
var locale=document.documentElement.lang==='en'?'en':'zh';
function t(key,params){
var value=dictionaries[locale][key];
if(value==null)throw new Error('Missing translation: '+locale+'.'+key);
return value.replace(/\{(\w+)\}/g,function(_,name){return params&&params[name]!=null?String(params[name]):'';});
}
global.ModelSelectorI18n={locale:locale,t:t,dictionaries:dictionaries};
})(window);
