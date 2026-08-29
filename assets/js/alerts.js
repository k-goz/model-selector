(function(global){
'use strict';
var SUB_KEY='ms_price_alert_subscriptions_v1';
var SNAPSHOT_KEY='ms_price_alert_snapshot_v1';
var DELIVERY_KEY='ms_price_alert_deliveries_v1';
var PENDING_KEY='ms_price_alert_pending_v1';
var previousFocus=null;
var customTransport=null;

function read(key,fallback){try{return JSON.parse(localStorage.getItem(key)||'null')||fallback;}catch(error){return fallback;}}
function write(key,value){localStorage.setItem(key,JSON.stringify(value));}
function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function id(){return 'sub_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,8);}
function analytics(name,properties){if(global.ModelSelectorAnalytics)global.ModelSelectorAnalytics.track(name,properties);}
function models(){return Array.isArray(global.catalogModels)?global.catalogModels:[];}
function modelKey(model){return model.provider_offering_id||[model.platform_id,model.name].join('/');}
function status(model){return model.price_status||'unknown';}
function lifecycle(model){return (model.lifecycle&&model.lifecycle.status)||'active';}
function price(model){
  var value=Number(model.input_price);
  return Number.isFinite(value)&&value>=0?value:null;
}
function snapshot(list){
  var out={};
  list.forEach(function(model){out[modelKey(model)]={
    key:modelKey(model),name:model.name,platformId:model.platform_id,platformName:model.platform_name,
    canonicalId:model.canonical_model_id||'',price:price(model),currency:model.currency||'',unit:model.price_unit||'',
    status:status(model),lifecycle:lifecycle(model),collectedAt:model.collected_at||''
  };});
  return out;
}
function scopeMatches(sub,item){
  if(sub.kind==='model'||sub.kind==='drop')return item.key===sub.target;
  if(sub.kind==='canonical')return item.canonicalId===sub.target;
  if(sub.kind==='platform')return item.platformId===sub.target;
  return true;
}
function changedEvents(sub,before,after){
  var events=[];
  Object.keys(after).forEach(function(key){
    var current=after[key],prior=before[key];
    if(!scopeMatches(sub,current))return;
    if(sub.kind==='new'&&!prior)events.push({key:key+':new',title:'新模型上线',body:current.platformName+' · '+current.name});
    if(!prior)return;
    if(sub.kind==='free'&&['free','free_tier'].indexOf(prior.status)===-1&&['free','free_tier'].indexOf(current.status)!==-1)events.push({key:key+':free',title:'模型出现免费状态',body:current.platformName+' · '+current.name});
    if(sub.kind==='retired'&&prior.lifecycle!=='retired'&&current.lifecycle==='retired')events.push({key:key+':retired',title:'模型已退役',body:current.platformName+' · '+current.name});
    if(sub.kind==='drop'&&prior.price>0&&current.price!=null&&current.price<prior.price){
      var pct=(prior.price-current.price)/prior.price*100;
      if(pct>=Number(sub.threshold||5))events.push({key:key+':drop:'+current.price,title:'模型降价 '+pct.toFixed(1)+'%',body:current.platformName+' · '+current.name});
    }
    if(['model','canonical','platform'].indexOf(sub.kind)!==-1){
      var priceChanged=prior.price>0&&current.price!=null&&Math.abs(current.price-prior.price)/prior.price>=0.01;
      if(priceChanged||prior.status!==current.status||prior.lifecycle!==current.lifecycle){
        events.push({key:key+':change:'+current.price+':'+current.status+':'+current.lifecycle,title:'模型状态变化',body:current.platformName+' · '+current.name});
      }
    }
  });
  if(sub.kind==='retired')Object.keys(before).forEach(function(key){
    var prior=before[key];if(!after[key]&&scopeMatches(sub,prior))events.push({key:key+':removed',title:'模型从目录移除',body:prior.platformName+' · '+prior.name});
  });
  return events;
}
function deliveries(){return read(DELIVERY_KEY,[]);}
function record(entry){var list=deliveries();list.unshift(entry);write(DELIVERY_KEY,list.slice(0,100));renderSubscriptions();}
function canSend(sub,now){return sub.frequency!=='daily'||!sub.lastSentAt||now-new Date(sub.lastSentAt).getTime()>=86400000;}
async function notify(sub,event,isTest,queueFailure){
  var eventId=(isTest?'test:':sub.id+':')+event.key;
  if(!isTest&&deliveries().some(function(item){return item.eventId===eventId&&item.status==='sent';}))return false;
  try{
    var options={body:event.body,tag:eventId,icon:'/assets/wechat-qr.jpg'};
    if(customTransport)await customTransport(event.title,options);
    else{
      if(!('Notification' in global))throw new Error('unsupported');
      var permission=Notification.permission;
      if(permission==='default')permission=await Notification.requestPermission();
      if(permission!=='granted')throw new Error('permission_'+permission);
      if('serviceWorker' in navigator){await navigator.serviceWorker.register('/sw.js');var registration=await navigator.serviceWorker.ready;await registration.showNotification(event.title,options);}
      else new Notification(event.title,options);
    }
    var sentAt=new Date().toISOString();
    record({eventId:eventId,subscriptionId:sub.id,status:'sent',title:event.title,sentAt:sentAt,channel:'browser'});
    if(!isTest){sub.lastSentAt=sentAt;analytics('price_alert_delivered',{kind:sub.kind,channel:'browser'});}
    return true;
  }catch(error){
    if(queueFailure!==false){var pending=read(PENDING_KEY,[]),existing=pending.find(function(item){return item.eventId===eventId;});
    if(!existing)pending.push({eventId:eventId,subscriptionId:sub.id,event:event,retries:0});write(PENDING_KEY,pending.slice(-50));}
    record({eventId:eventId,subscriptionId:sub.id,status:'failed',title:event.title,sentAt:new Date().toISOString(),channel:'browser',reason:String(error.message||error)});
    return false;
  }
}
async function retryPending(subscriptions){
  var pending=read(PENDING_KEY,[]),remaining=[];
  for(var i=0;i<pending.length;i++){
    var item=pending[i],sub=subscriptions.find(function(candidate){return candidate.id===item.subscriptionId&&candidate.active;});
    if(!sub||item.retries>=3)continue;
    item.retries+=1;
    if(!(await notify(sub,item.event,false,false)))remaining.push(item);
  }
  write(PENDING_KEY,remaining);
}
async function evaluate(){
  var list=models();if(!list.length)return;
  var current=snapshot(list),prior=read(SNAPSHOT_KEY,{}),subscriptions=read(SUB_KEY,[]),now=Date.now();
  await retryPending(subscriptions);
  for(var i=0;i<subscriptions.length;i++){
    var sub=subscriptions[i];if(!sub.active||!canSend(sub,now))continue;
    var events=changedEvents(sub,prior,current);
    if(events.length)await notify(sub,events[0],false);
  }
  write(SUB_KEY,subscriptions);write(SNAPSHOT_KEY,current);renderSubscriptions();
}
function kindLabel(kind){return {model:'具体模型',canonical:'标准模型（跨平台）',platform:'平台全部模型',free:'免费状态变化',new:'新模型上线',retired:'模型退役',drop:'降价阈值'}[kind]||kind;}
function targetOptions(kind){
  var list=models(),seen={},options=[];
  if(['free','new','retired'].indexOf(kind)!==-1)return '<option value="all">全部模型</option>';
  list.forEach(function(model){
    var value,label;
    if(kind==='platform'){value=model.platform_id;label=model.platform_name;}
    else if(kind==='canonical'){value=model.canonical_model_id||'';label=(model.model_family||model.name)+' · '+value;}
    else{value=modelKey(model);label=model.platform_name+' · '+model.name;}
    if(value&&!seen[value]){seen[value]=true;options.push({value:value,label:label});}
  });
  options.sort(function(a,b){return a.label.localeCompare(b.label,'zh-CN');});
  return options.map(function(option){return '<option value="'+esc(option.value)+'">'+esc(option.label)+'</option>';}).join('');
}
function updateTargets(){
  var kind=document.getElementById('alertKind').value,target=document.getElementById('alertTarget');
  target.innerHTML=targetOptions(kind);target.disabled=['free','new','retired'].indexOf(kind)!==-1;
  document.getElementById('alertThresholdRow').hidden=kind!=='drop';
}
function renderSubscriptions(){
  var host=document.getElementById('alertSubscriptions');if(!host)return;
  var subscriptions=read(SUB_KEY,[]),logs=deliveries().slice(0,5);
  host.innerHTML='<h3>我的订阅</h3>'+(subscriptions.length?subscriptions.map(function(sub){return '<div class="alert-item"><span><strong>'+esc(kindLabel(sub.kind))+'</strong><small>'+esc(sub.targetLabel||sub.target)+' · '+esc(sub.frequency==='daily'?'每日最多一次':'检测到即通知')+'</small></span><button type="button" data-remove="'+esc(sub.id)+'">退订</button></div>';}).join(''):'<p class="alert-empty">尚未创建订阅</p>')+
    '<h3>最近发送记录</h3>'+(logs.length?logs.map(function(log){return '<div class="alert-log"><span class="alert-status '+esc(log.status)+'">'+esc(log.status==='sent'?'已发送':'待重试')+'</span>'+esc(log.title)+'<time>'+esc((log.sentAt||'').slice(0,19).replace('T',' '))+'</time></div>';}).join(''):'<p class="alert-empty">暂无发送记录</p>');
  host.querySelectorAll('[data-remove]').forEach(function(button){button.addEventListener('click',function(){removeSubscription(button.dataset.remove);});});
}
function addSubscription(){
  var kind=document.getElementById('alertKind').value,target=document.getElementById('alertTarget');
  if(!target.value)return;
  var subscriptions=read(SUB_KEY,[]),sub={id:id(),kind:kind,target:target.value,targetLabel:target.options[target.selectedIndex].text,threshold:Number(document.getElementById('alertThreshold').value||5),frequency:document.getElementById('alertFrequency').value,active:true,createdAt:new Date().toISOString(),lastSentAt:null};
  subscriptions.push(sub);write(SUB_KEY,subscriptions);write(SNAPSHOT_KEY,snapshot(models()));renderSubscriptions();
  analytics('price_subscription_created',{kind:kind,channel:'browser'});if(global.showToast)global.showToast('价格订阅已创建');
}
function removeSubscription(subscriptionId){
  var subscriptions=read(SUB_KEY,[]).filter(function(sub){return sub.id!==subscriptionId;});write(SUB_KEY,subscriptions);renderSubscriptions();analytics('price_subscription_removed',{channel:'browser'});
}
async function testNotification(){
  var testSub={id:'test',kind:'test',frequency:'immediate'};
  var ok=await notify(testSub,{key:String(Date.now()),title:'AI 模型选择器：通知测试',body:'浏览器价格提醒渠道已连接。'},true);
  if(global.showToast)global.showToast(ok?'测试通知已发送':'通知未发送，请检查浏览器权限');
}
function openModal(){previousFocus=document.activeElement;document.getElementById('alertModal').classList.add('show');updateTargets();renderSubscriptions();document.getElementById('alertKind').focus();}
function closeModal(){document.getElementById('alertModal').classList.remove('show');if(previousFocus)previousFocus.focus();}
function mount(){
  var toolbar=document.querySelector('.toolbar');if(toolbar){var button=document.createElement('button');button.type='button';button.className='tool-btn';button.id='priceAlertBtn';button.textContent='🔔 订阅';button.addEventListener('click',openModal);toolbar.appendChild(button);}
  document.body.insertAdjacentHTML('beforeend','<div class="tk-modal alert-modal" id="alertModal" role="dialog" aria-modal="true" aria-labelledby="alertModalTitle"><div class="tk-modal-content"><div class="tk-modal-header"><div class="tk-modal-title" id="alertModalTitle">🔔 价格变化订阅</div><button type="button" class="tk-modal-close" id="alertClose" aria-label="关闭价格订阅">×</button></div><div class="tk-modal-body"><p class="alert-note">浏览器本地通知：不上传订阅或个人数据；网站打开时检测新版本并通知。清除浏览器数据会移除订阅。</p><div class="alert-form"><label>订阅类型<select id="alertKind"><option value="model">具体模型</option><option value="canonical">标准模型（跨平台）</option><option value="platform">某个平台</option><option value="free">免费状态变化</option><option value="new">新模型上线</option><option value="retired">模型退役</option><option value="drop">价格下降超过阈值</option></select></label><label>范围<select id="alertTarget"></select></label><label id="alertThresholdRow" hidden>降价阈值（%）<input id="alertThreshold" type="number" min="1" max="90" value="10"></label><label>频率<select id="alertFrequency"><option value="daily">每日最多一次</option><option value="immediate">检测到即通知</option></select></label><div class="alert-actions"><button type="button" class="tk-btn" id="alertCreate">创建订阅</button><button type="button" class="tk-btn tk-btn-sec" id="alertTest">发送测试通知</button></div></div><div id="alertSubscriptions"></div></div></div></div>');
  document.getElementById('alertKind').addEventListener('change',updateTargets);document.getElementById('alertCreate').addEventListener('click',addSubscription);document.getElementById('alertTest').addEventListener('click',testNotification);document.getElementById('alertClose').addEventListener('click',closeModal);document.getElementById('alertModal').addEventListener('click',function(event){if(event.target===this)closeModal();});
  var attempts=0,timer=setInterval(function(){attempts+=1;if(models().length){clearInterval(timer);updateTargets();evaluate();}else if(attempts>100)clearInterval(timer);},100);
}
document.addEventListener('DOMContentLoaded',mount);
global.ModelSelectorAlerts={evaluate:evaluate,open:openModal,subscriptions:function(){return read(SUB_KEY,[]);},deliveries:deliveries,setTransport:function(transport){customTransport=transport;}};
})(window);
