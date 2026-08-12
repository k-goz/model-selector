
var curP='all',curS='all',curPT='all',curSort='default',selModels=[];
var curTags=[],curCtx='all',curCur='CNY',priceMin=null,priceMax=null;
var curFamily='all';
var isDark=localStorage.getItem('dark')!=='0';
var isListView=localStorage.getItem('listView')==='1';
var favs=JSON.parse(localStorage.getItem('favs')||'[]');
var USD_TO_CNY=7.25;

// ─── 从 models_data.json 动态加载模型数据 ───
var modelsDataLoaded = false;
function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function classifyModelPrice(model, tags) {
    var inp = parseFloat(model.input_price) || 0;
    var out = parseFloat(model.output_price) || 0;
    var status = model.price_status || '';
    var billingUnit = model.billing_unit || '';
    if (!status) {
        if (inp > 0 || out > 0) status = 'priced';
        else if (tags.indexOf('已下线') >= 0) status = 'unavailable';
        else if (tags.indexOf('即将下线') >= 0) status = 'retiring';
        else if (tags.indexOf('按次计费') >= 0) status = 'non_token';
        else if (tags.indexOf('免费') >= 0) status = 'free';
        else if (tags.indexOf('免费额度') >= 0) status = 'free_tier';
        else if (model.scene === '图片生成' || model.scene === '视频生成') status = 'non_token';
        else status = 'unknown';
    }
    if (!billingUnit) billingUnit = status === 'priced' || status === 'free' ? 'token' : (tags.indexOf('按次计费') >= 0 ? 'request' : 'unknown');
    var labels = {free:'免费',free_tier:'有免费额度 · 价格待确认',non_token:'非 Token 计费 · 待确认',
        unavailable:'已下线',retiring:'即将下线',unknown:'价格待确认'};
    return {status:status,billingUnit:billingUnit,label:labels[status] || ''};
}
function renderModelsFromJSON(data) {
    var grid = document.getElementById('grid');
    if (!grid || !data || !data.models) return false;
    // 清空现有卡片
    grid.innerHTML = '';
    var models = data.models;
    var meta = data.meta || {};
    // 更新汇率
    if (meta.usd_to_cny) USD_TO_CNY = meta.usd_to_cny;
    // 更新数据说明中的时间
    var timeEls = document.querySelectorAll('.ftr p, .snote');
    // 动态生成卡片
    for (var i = 0; i < models.length; i++) {
        var m = models[i];
        var pid = m.platform_id;
        var pname = String(m.platform_name || '');
        var pc = m.platform_color;
        if(!pc && data.platforms && data.platforms[pid]) pc = data.platforms[pid].color;
        if(!/^#[0-9a-f]{3,8}$/i.test(pc || '')) pc = '#6366f1';
        var mname = String(m.name || '');
        var inp = m.input_price;
        var out = m.output_price;
        var ctx = String(m.context || 'N/A');
        var tags = m.tags || [];
        var scen = m.scene || '日常对话';
        var fam = m.family || '';
        var cur = m.currency || 'CNY';
        var pu = m.price_unit || 'per_token';
        var baseUrl = String(m.base_url || '');
        var priceInfo = classifyModelPrice(m, tags);
        var priceStatus = priceInfo.status;
        var billingUnit = priceInfo.billingUnit;

        // 价格分级
        var pt = 'mid';
        var inpF = parseFloat(inp) || 0, outF = parseFloat(out) || 0;
        if (priceStatus === 'free' || priceStatus === 'free_tier') pt = 'free';
        else if (priceStatus !== 'priced') pt = 'unknown';
        else if (cur === 'USD' && pu === 'per_token') { var p = inpF * 1e6; pt = p < 0.1 ? 'cheap' : p < 10 ? 'mid' : p < 100 ? 'high' : 'ultra'; }
        else { pt = inpF < 0.1 ? 'cheap' : inpF < 10 ? 'mid' : inpF < 100 ? 'high' : 'ultra'; }

        // data-inp/data-out
        var inpS, outS;
        if (pu === 'per_1m' && cur === 'USD') { inpS = inpF / 1e6; outS = outF / 1e6; }
        else { inpS = inpF; outS = outF; }

        // 上下文数值
        var ctxNum = ctx.replace(/[^\d]/g, '') || '0';

        // 标签 HTML
        var tagMap = {'免费':'free','免费额度':'free','便宜':'cheap','极便宜':'cheap','性价比':'cheap',
            '旗舰':'hot','主力':'hot','最新版':'hot','2025新':'hot','2026新':'hot',
            '视觉':'vision','推理':'reason','长上下文':'long','超长上下文':'long',
            '开源':'other','代码':'other','图片生成':'other','视频生成':'other',
            '快速':'other','高性能':'hot','Pro订阅':'other','蒸馏':'other',
            '轻量':'other','已下线':'other','即将下线':'other','价格待确认':'other',
            '语音':'other','TTS':'other','ASR':'other','向量':'other','排序':'other',
            'OCR':'other','多模态':'vision','Turbo':'hot','降价后':'cheap','降价90%':'cheap',
            '超低价':'cheap','超便宜':'cheap','编程':'other','智能路由':'other',
            '满血版':'hot','价格变动':'other','涨价':'hot','降价':'cheap','免费':'free'};
        var tagsHtml = '';
        for (var ti = 0; ti < tags.length; ti++) {
            var tc = tagMap[tags[ti]] || 'other';
            tagsHtml += '<span class="tg tg-' + tc + '">' + escapeHtml(tags[ti]) + '</span>';
        }

        // 价格徽章
        var priceHtml = '';
        if (priceStatus !== 'priced') {
            var statusClass = priceStatus === 'free' ? 'price-free' : 'price-unknown';
            priceHtml = '<span class="price-badge ' + statusClass + '">' + escapeHtml(priceInfo.label) + '</span>';
        } else if (cur === 'CNY') {
            if (inpF === outF) { var cc2 = inpF < 1 ? 'price-cheap' : inpF < 10 ? 'price-mid' : inpF < 100 ? 'price-high' : 'price-ultra'; priceHtml = '<span class="price-badge ' + cc2 + '">¥' + inpF.toFixed(2) + '/M</span>'; }
            else priceHtml = '<span class="price-badge price-mid">IN:¥' + inpF.toFixed(2) + ' OUT:¥' + outF.toFixed(2) + '/M</span>';
        } else {
            var pI = pu === 'per_token' ? inpF * 1e6 : inpF;
            var pO = pu === 'per_token' ? outF * 1e6 : outF;
            if (inpF === outF) { var cc3 = pI < 0.1 ? 'price-free' : pI < 1 ? 'price-cheap' : pI < 10 ? 'price-mid' : pI < 100 ? 'price-high' : 'price-ultra'; priceHtml = '<span class="price-badge ' + cc3 + '">$' + pI.toFixed(2) + '/1M</span>'; }
            else priceHtml = '<span class="price-badge price-mid">IN:$' + pI.toFixed(1) + ' OUT:$' + pO.toFixed(1) + '/1M</span>';
        }

        var sourceMap = {A:'API实时',H:'硬编码(可能过时)',P:'代理平台自营价(非官方)',S:'官方定价页爬取',
            SP:'SPA页面爬取',OR:'OpenRouter回填',L:'LiteLLM社区数据',DB:'官方价格数据库',CV:'交叉验证修正'};
        var priceSrc = String(m.price_src || '');
        var sourceHtml = priceSrc ? '<span class="price-src' + (priceSrc === 'P' ? ' price-src-proxy' : '')
            + '" title="价格来源: ' + escapeHtml(sourceMap[priceSrc] || priceSrc) + '">' + escapeHtml(priceSrc.slice(0,1)) + '</span>' : '';

        // 上下文条
        var ctxBarW = Math.min(100, (parseInt(ctxNum) || 0) / 1000);

        // 家族属性
        var famAttr = fam ? ' data-family="' + escapeHtml(fam) + '"' : '';

        // 构建卡片 HTML
        var cardHtml = '<div class="mc" style="--c:' + pc + '" data-s="' + escapeHtml(scen) + '" data-p="' + escapeHtml(pid) + '" data-pt="' + pt + '" '
            + 'data-inp="' + inpS + '" data-out="' + outS + '" data-cur="' + cur + '" data-pu="' + pu + '" '
            + 'data-ctx="' + ctxNum + '" data-ctx-display="' + escapeHtml(ctx) + '" data-price-status="' + priceStatus + '" '
            + 'data-billing-unit="' + billingUnit + '" data-base-url="' + escapeHtml(baseUrl) + '" '
            + 'data-model-name="' + escapeHtml(mname) + '" ' + famAttr + ' '
            + 'onclick="showCodeModal(this.dataset.baseUrl,this.dataset.modelName,this.dataset.p)">'
            + '<div class="dot"></div><div class="prov">' + escapeHtml(pname) + '</div>'
            + '<div class="mname">' + escapeHtml(mname) + '</div><div class="tags">' + tagsHtml + '</div>'
            + '<div class="prow">' + priceHtml + sourceHtml + '</div>'
            + '<div class="ctx-row"><span class="ctx">上下文: ' + escapeHtml(ctx) + '</span>'
            + '<div class="ctx-bar-wrap"><div class="ctx-bar" style="width:' + ctxBarW + '%"></div></div></div>'
            + '<div class="base-url">' + escapeHtml(baseUrl) + '</div>'
            + '<div class="hint">点击查看接入代码</div>'
            + '<div class="card-actions">'
            + '<span class="fav-btn" onclick="event.stopPropagation();toggleFav(this)" title="收藏">&#9734;</span>'
            + '<div class="cb-wrap"><input type="checkbox" class="mc-cb" onclick="event.stopPropagation();toggleSel(this)"><label class="cb-lbl">对比</label></div>'
            + '</div></div>';

        grid.insertAdjacentHTML('beforeend', cardHtml);
    }

    // 更新模型计数
    var bdEls = document.querySelectorAll('.bd');
    if (bdEls.length > 0) bdEls[0].innerHTML = '&#128202; ' + models.length + ' 个模型';
    var fcEl = document.querySelector('.filter-count');
    if (fcEl) fcEl.innerHTML = '显示 <strong>' + models.length + '</strong> / ' + models.length + ' 个模型';

    // 更新平台筛选栏计数
    if (meta.platform_counts) {
        var pc2 = meta.platform_counts;
        document.querySelectorAll('.pt').forEach(function(b) {
            var p = b.dataset.p;
            var span = b.querySelector('.pc');
            if (span && pc2[p]) span.textContent = pc2[p];
        });
    }

    modelsDataLoaded = true;
    favs.forEach(function(f){var c=findCardByName(f);if(c){c.classList.add('fav-card');var fb=c.querySelector('.fav-btn');if(fb)fb.classList.add('active');}});
    return true;
}

// 初始化
document.addEventListener('DOMContentLoaded',function(){
// ─── 尝试从 models_data.json 动态加载 ───
fetch('models_data.json').then(function(r){return r.json();}).then(function(data){
    if(data && data.models && data.models.length>0){
        renderModelsFromJSON(data);
        filter();
    }
}).catch(function(){
    // JSON 加载失败，使用 HTML 中已有的硬编码卡片
});

if(!isDark)document.body.classList.add('light');
if(isListView){document.getElementById('grid').classList.add('list-view');document.getElementById('listBtn').classList.add('active');}
// 恢复收藏
favs.forEach(function(f){var c=findCardByName(f);if(c){c.classList.add('fav-card');var fb=c.querySelector('.fav-btn');if(fb)fb.classList.add('active');}});
// 加载动画
var ld=document.getElementById('ld');ld.classList.add('show');
setTimeout(function(){ld.classList.remove('show')},600);
// 平台筛选
document.querySelectorAll('.pt').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curP=b.dataset.p;filter();saveState();});});
// 价格分级筛选
document.querySelectorAll('.pt-filter').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.pt-filter').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curPT=b.dataset.pt;filter();saveState();});});
// 场景筛选
document.querySelectorAll('.sc').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curS=b.dataset.sc;filter();saveState();});});
// 排序
document.querySelectorAll('.sort-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.sort-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curSort=b.dataset.sort;sortCards();});});
// 标签筛选
document.querySelectorAll('.tag-btn').forEach(function(b){b.addEventListener('click',function(){
b.classList.toggle('active');
curTags=Array.from(document.querySelectorAll('.tag-btn.active')).map(function(x){return x.dataset.tag;});
filter();saveState();});});
// 上下文筛选
document.querySelectorAll('.ctx-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.ctx-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curCtx=b.dataset.ctx;filter();saveState();});});
// 家族筛选
document.querySelectorAll('.family-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.family-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curFamily=b.dataset.family;filter();saveState();});});
// 货币切换
document.querySelectorAll('.cur-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.cur-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');curCur=b.dataset.cur;updatePrices();});});
// 搜索
var st;
document.getElementById('si').addEventListener('input',function(){clearTimeout(st);st=setTimeout(function(){filter();saveState();},200)});
// 预设按钮
document.querySelectorAll('.preset-btn').forEach(function(b){b.addEventListener('click',function(){
document.getElementById('calcChats').value=b.dataset.chats;
document.getElementById('calcTokens').value=b.dataset.tokens;
document.getElementById('calcRatio').value=b.dataset.ratio;});});
// 智能推荐
document.querySelectorAll('.rec-btn').forEach(function(b){b.addEventListener('click',function(){
document.querySelectorAll('.rec-btn').forEach(function(x){x.classList.remove('active')});
b.classList.add('active');runRecommend(b.dataset.rec);});});
// 键盘快捷键
document.addEventListener('keydown',function(e){
if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();document.getElementById('si').focus()}
if(e.key==='Escape'){
// 先关闭代码模态框，再清空搜索
var cm=document.getElementById('codeModal');
if(cm&&cm.classList.contains('show')){closeCodeModal();return;}
document.getElementById('si').blur();document.getElementById('si').value='';filter();
}
if(e.key==='d'&&!e.ctrlKey&&document.activeElement.tagName!=='INPUT'){toggleDark();}
if(e.key==='v'&&!e.ctrlKey&&document.activeElement.tagName!=='INPUT'){toggleView();}
// 数字键1-9快速切换平台
var platforms=['all','openrouter','aliyun','siliconflow','moonshot','zhipu','volcengine','baidu','tencent'];
var num=parseInt(e.key);
if(num>=1&&num<=9&&document.activeElement.tagName!=='INPUT'){
var pb=document.querySelector('.pt[data-p="'+platforms[num-1]+'"]');
if(pb)pb.click();
}
});
// 从URL hash恢复状态
restoreState();

// 初始筛选
filter();
// 生成跨平台比价
buildCrossPrice();
});

function findCardByName(name){
var cards=document.querySelectorAll('.mc');
for(var i=0;i<cards.length;i++){
var mn=(cards[i].querySelector('.mname')||{}).textContent||'';
if(mn===name)return cards[i];
}return null;
}

// ─── 高级搜索语法解析 ───
function parseAdvancedSearch(q){
var result={text:'',priceMin:null,priceMax:null,ctxMin:null,ctxMax:null,family:null,platform:null};
if(!q)return result;
var parts=q.split(/\s+/);
var textParts=[];
parts.forEach(function(p){
// price<1 或 price>5 或 price=2
var priceMatch=p.match(/^price\s*([<>=])\s*([\d.]+)$/i);
if(priceMatch){
var op=priceMatch[1],val=parseFloat(priceMatch[2]);
if(op==='<')result.priceMax=val;
else if(op==='>')result.priceMin=val;
else if(op==='='){result.priceMin=val;result.priceMax=val;}
return;
}
// ctx>128 或 ctx<32 或 ctx=64
var ctxMatch=p.match(/^ctx\s*([<>=])\s*(\d+)$/i);
if(ctxMatch){
var op=ctxMatch[1],val=parseInt(ctxMatch[2]);
if(op==='<')result.ctxMax=val;
else if(op==='>')result.ctxMin=val;
else if(op==='='){result.ctxMin=val;result.ctxMax=val;}
return;
}
// family:GPT
var famMatch=p.match(/^family[:=]\s*(\S+)$/i);
if(famMatch){result.family=famMatch[1];return;}
// platform:aliyun
var platMatch=p.match(/^platform[:=]\s*(\S+)$/i);
if(platMatch){result.platform=platMatch[1].toLowerCase();return;}
textParts.push(p);
});
result.text=textParts.join(' ');
return result;
}

// ─── 筛选 ───
function filter(){
var cs=document.querySelectorAll('.mc');
var q=(document.getElementById('si').value||'').toLowerCase().trim();
var n=0;
cs.forEach(function(c){
var sh=true;
var pn=(c.querySelector('.prov')||{}).textContent||'';
var mn=(c.querySelector('.mname')||{}).textContent||'';
if(curP!='all'&&curP!==(c.dataset.p||''))sh=false;
if(curPT!='all'&&curPT!==(c.dataset.pt||''))sh=false;
if(curS!='all'&&curS!==(c.dataset.s||''))sh=false;
// 标签筛选
if(curTags.length>0){
var cardTags=Array.from(c.querySelectorAll('.tg')).map(function(t){return t.textContent;});
var match=curTags.some(function(t){return cardTags.indexOf(t)!==-1;});
if(!match)sh=false;
}
// 上下文筛选
if(curCtx!=='all'){
var ctxVal=parseInt(c.dataset.ctx||0);
var ctxMin=parseInt(curCtx)*1000;
if(ctxVal<ctxMin)sh=false;
}
// 家族筛选
if(curFamily!=='all'){
var fam=c.dataset.family||'';
if(fam!==curFamily)sh=false;
}
// 价格区间筛选
var inp=parseFloat(c.dataset.inp||0);
var cur=c.dataset.cur||'CNY';
var pu2=c.dataset.pu||'per_token';
var mul=cur==='USD'?(pu2==='per_1m'?1:1e6):1;
var cnyInp=cur==='USD'?inp*mul*USD_TO_CNY:inp;
if(priceMin!==null||priceMax!==null){
if(priceMin!==null&&cnyInp<priceMin)sh=false;
if(priceMax!==null&&cnyInp>priceMax)sh=false;
}
 // 搜索 (支持高级语法)
 if(q){
 var adv=parseAdvancedSearch(q);
 // 模糊匹配: 搜索词每个字符按序出现即可 (如 "dsk" 匹配 "deepseek")
 function fuzzyMatch(text,query){var t=text.toLowerCase(),q2=query.toLowerCase(),ti=0;for(var qi=0;qi<q2.length;qi++){ti=t.indexOf(q2[qi],ti);if(ti===-1)return false;ti++;}return true;}
 if(adv.text&&!fuzzyMatch(mn,adv.text)&&!fuzzyMatch(pn,adv.text))sh=false;
// 高级价格筛选
if(adv.priceMin!==null){
if(cnyInp<adv.priceMin)sh=false;
}
if(adv.priceMax!==null){
if(cnyInp>adv.priceMax)sh=false;
}
// 高级上下文筛选
if(adv.ctxMin!==null){
var ctxK=parseInt(c.dataset.ctx||0)/1000;
if(ctxK<adv.ctxMin)sh=false;
}
if(adv.ctxMax!==null){
var ctxK2=parseInt(c.dataset.ctx||0)/1000;
if(ctxK2>adv.ctxMax)sh=false;
}
// 高级家族筛选
if(adv.family){
var fam2=(c.dataset.family||'').toLowerCase();
if(fam2!==adv.family.toLowerCase())sh=false;
}
// 高级平台筛选
if(adv.platform){
if((c.dataset.p||'')!==adv.platform)sh=false;
}
}
c.setAttribute('data-visible',sh?'1':'0');
c.style.display=sh?'':'none';if(sh)n++;
});
document.getElementById('empty').style.display=n===0?'block':'none';
// 更新筛选计数
totalFiltered=n;
currentPage=1;
// Apply pagination based on data-visible
var visIdx=0;
cs.forEach(function(c){
    if(c.getAttribute('data-visible')==='1'){
        var page=Math.floor(visIdx/PAGE_SIZE)+1;
        c.style.display=(page===currentPage)?'':'none';
        visIdx++;
    }
});
var fc=document.getElementById('filterCount');
if(fc)fc.innerHTML='显示 <strong>'+n+'</strong> / '+cs.length+' 个模型';
renderPagination();
}

// ─── 分页 ───
var PAGE_SIZE=66;
var currentPage=1;
var totalFiltered=0;

function renderPagination(){
    var totalPages=Math.ceil(totalFiltered/PAGE_SIZE)||1;
    if(currentPage>totalPages)currentPage=totalPages;
    var pg=document.getElementById('pagination');
    if(!pg)return;
    if(totalPages<=1){pg.innerHTML='';return;}
    var h='';
    h+='<button class="page-btn" onclick="goPage(1)"'+(currentPage===1?' disabled':'')+'>&laquo; 首页</button>';
    h+='<button class="page-btn" onclick="goPage('+(currentPage-1)+')"'+(currentPage===1?' disabled':'')+'>&lsaquo; 上一页</button>';
    var start=Math.max(1,currentPage-3);
    var end=Math.min(totalPages,currentPage+3);
    if(start>1)h+='<span class="page-info">...</span>';
    for(var i=start;i<=end;i++){
        h+='<button class="page-btn'+(i===currentPage?' active':'')+'" onclick="goPage('+i+')">'+i+'</button>';
    }
    if(end<totalPages)h+='<span class="page-info">...</span>';
    h+='<button class="page-btn" onclick="goPage('+(currentPage+1)+')"'+(currentPage===totalPages?' disabled':'')+'>下一页 &rsaquo;</button>';
    h+='<button class="page-btn" onclick="goPage('+totalPages+')"'+(currentPage===totalPages?' disabled':'')+'>末页 &raquo;</button>';
    h+='<span class="page-info">第 '+currentPage+' / '+totalPages+' 页 (共 '+totalFiltered+' 个)</span>';
    pg.innerHTML=h;
}

function goPage(p){
    var totalPages=Math.ceil(totalFiltered/PAGE_SIZE)||1;
    if(p<1)p=1;if(p>totalPages)p=totalPages;
    currentPage=p;
    applyPage();
    renderPagination();
    document.querySelector('.grid').scrollIntoView({behavior:'smooth',block:'start'});
}

function applyPage(){
    var cards=document.querySelectorAll('.mc');
    var vis=0;
    cards.forEach(function(c){
        if(c.getAttribute('data-visible')==='1'){
            var page=Math.floor(vis/PAGE_SIZE)+1;
            var show=(page===currentPage);
            c.style.display=show?'':'none';
            vis++;
        }
    });
}

// ─── 排序 ───
function sortCards(){
var grid=document.getElementById('grid');
var cs=Array.from(grid.querySelectorAll('.mc'));
function comparable(c){return c.dataset.priceStatus==='priced'||c.dataset.priceStatus==='free'}
function priceCompare(a,b,field,desc){
var ac=comparable(a),bc=comparable(b);
if(ac!==bc)return ac?-1:1;
if(!ac)return 0;
var av=parseFloat(a.dataset[field])||0,bv=parseFloat(b.dataset[field])||0;
return desc?bv-av:av-bv;
}
var sortFn={
'default':function(){return 0},
'inp-asc':function(a,b){return priceCompare(a,b,'inp',false)},
'inp-desc':function(a,b){return priceCompare(a,b,'inp',true)},
'out-asc':function(a,b){return priceCompare(a,b,'out',false)},
'out-desc':function(a,b){return priceCompare(a,b,'out',true)},
'name':function(a,b){return (a.querySelector('.mname')||{}).textContent.localeCompare((b.querySelector('.mname')||{}).textContent)},
'combined':function(a,b){
var ai=parseFloat(a.dataset.inp)||0,ao=parseFloat(a.dataset.out)||0;
var bi=parseFloat(b.dataset.inp)||0,bo=parseFloat(b.dataset.out)||0;
return (ai+ao*0.5)-(bi+bo*0.5);
},
'ctx':function(a,b){return (parseInt(b.dataset.ctx)||0)-(parseInt(a.dataset.ctx)||0)},
'costperf':function(a,b){
// 性价比 = 上下文长度 / (输入价+输出价*0.5)，越大越好
var ai=parseFloat(a.dataset.inp)||0,ao=parseFloat(a.dataset.out)||0,ac2=parseInt(a.dataset.ctx)||1;
var bi=parseFloat(b.dataset.inp)||0,bo=parseFloat(b.dataset.out)||0,bc2=parseInt(b.dataset.ctx)||1;
var pa=(ai+ao*0.5)||0.001,pb=(bi+bo*0.5)||0.001;
return (bc2/pb)-(ac2/pa);
}
};
cs.sort(sortFn[curSort]||sortFn['default']);
cs.forEach(function(c){grid.appendChild(c)});
filter();
// Re-apply pagination after sort
applyPage();
renderPagination();
}

// ─── 货币切换 ───
function updatePrices(){
document.querySelectorAll('.mc').forEach(function(c){
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var prow=c.querySelector('.prow');
if(!prow)return;
if(c.dataset.priceStatus!=='priced')return;
var sourceBadge=prow.querySelector('.price-src');
var sourceHtml=sourceBadge?sourceBadge.outerHTML:'';
var pu=c.dataset.pu||'per_token';
if(curCur==='CNY'){
if(cur==='USD'){
var mul=pu==='per_1m'?1:1e6;
var cnyInp=inp*mul*USD_TO_CNY;
var cnyOut=out*mul*USD_TO_CNY;
prow.innerHTML=makeCNYBadge(cnyInp,cnyOut)+sourceHtml;
}else{
prow.innerHTML=makeCNYBadge(inp,out)+sourceHtml;
}
}else{
if(cur==='CNY'){
var usdInp=inp/USD_TO_CNY/1e6;
var usdOut=out/USD_TO_CNY/1e6;
prow.innerHTML=makeUSDBadge(usdInp,usdOut)+sourceHtml;
}else{
var mul2=pu==='per_1m'?1:1e6;
prow.innerHTML=makeUSDBadge(inp*mul2,out*mul2)+sourceHtml;
}
}
});
}
function makeCNYBadge(inp,out){
if(inp===0&&out===0)return '<span class="price-badge price-free">免费额度</span>';
if(Math.abs(inp-out)<0.01){
var c=inp<1?"price-cheap":inp<10?"price-mid":inp<100?"price-high":"price-ultra";
return '<span class="price-badge '+c+'">¥'+inp.toFixed(2)+'/M</span>';
}
return '<span class="price-badge price-mid">IN:¥'+inp.toFixed(2)+' OUT:¥'+out.toFixed(2)+'/M</span>';
}
function makeUSDBadge(inp,out){
if(inp===0&&out===0)return '<span class="price-badge price-free">$0 (免费)</span>';
if(Math.abs(inp-out)<0.01){
var c=inp<0.1?"price-free":inp<1?"price-cheap":inp<10?"price-mid":inp<100?"price-high":"price-ultra";
return '<span class="price-badge '+c+'">$'+inp.toFixed(2)+'/1M</span>';
}
return '<span class="price-badge price-mid">IN:$'+inp.toFixed(2)+' OUT:$'+out.toFixed(2)+'/1M</span>';
}

// ─── 收藏 ───
function toggleFav(btn){
btn.classList.toggle('active');
var c=btn.closest('.mc');
c.classList.toggle('fav-card');
var mn=(c.querySelector('.mname')||{}).textContent||'';
if(btn.classList.contains('active')){
if(favs.indexOf(mn)===-1)favs.push(mn);
}else{
var idx=favs.indexOf(mn);if(idx!==-1)favs.splice(idx,1);
}
localStorage.setItem('favs',JSON.stringify(favs));
}

// ─── 暗色模式 ───
function toggleDark(){
isDark=!isDark;
document.body.classList.toggle('light');
localStorage.setItem('dark',isDark?'1':'0');
}

// ─── 视图切换 ───
function toggleView(){
isListView=!isListView;
document.getElementById('grid').classList.toggle('list-view');
document.getElementById('listBtn').classList.toggle('active');
localStorage.setItem('listView',isListView?'1':'0');
}

// ─── 价格区间 ───
function applyPriceRange(){
priceMin=parseFloat(document.getElementById('priceMin').value)||null;
priceMax=parseFloat(document.getElementById('priceMax').value)||null;
filter();
}
function clearPriceRange(){
priceMin=null;priceMax=null;
document.getElementById('priceMin').value='';
document.getElementById('priceMax').value='';
filter();
}

// ─── 模型对比 ───
function toggleSel(cb){
var c=cb.closest('.mc');
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var ctx=c.dataset.ctxDisplay||'';
var priceStatus=c.dataset.priceStatus||'unknown';
var cmd=c.getAttribute('onclick')||'';
var mIdx=selModels.findIndex(function(m){return m.name===mName});
if(cb.checked){
if(selModels.length>=3){cb.checked=false;alert('最多选择3个模型对比');return}
if(mIdx===-1)selModels.push({name:mName,prov:prov,inp:inp,out:out,cur:cur,ctx:ctx,cmd:cmd,priceStatus:priceStatus});
}else{
if(mIdx!==-1)selModels.splice(mIdx,1);
}
updateCmpPanel();
}
function updateCmpPanel(){
var panel=document.getElementById('cmpPanel');
var list=document.getElementById('cmpList');
var count=document.getElementById('cmpCount');
count.textContent=selModels.length;
if(selModels.length===0){panel.style.display='none';return}
panel.style.display='block';
list.innerHTML=selModels.map(function(m,i){
var price=m.priceStatus==='priced'?(m.cur==='USD'?'$'+(m.inp*1e6).toFixed(2)+'/M':'¥'+m.inp.toFixed(2)+'/M'):(m.priceStatus==='free'?'免费':'价格待确认');
return '<div class="cmp-item"><span class="cmp-item-name">'+escapeHtml(m.name)+'</span>'
+'<span class="cmp-item-price">'+price+'</span>'
+'<button class="cmp-item-del" onclick="delSel('+i+')">&times;</button></div>';
}).join('');
}
function delSel(i){selModels.splice(i,1);updateCmpPanel();
var cbs=document.querySelectorAll('.mc-cb');cbs.forEach(function(cb){
var c=cb.closest('.mc');var n=(c.querySelector('.mname')||{}).textContent||'';
if(!selModels.find(function(m){return m.name===n}))cb.checked=false;
});}
function clearCmp(){selModels=[];updateCmpPanel();
document.querySelectorAll('.mc-cb').forEach(function(cb){cb.checked=false});}
function showCmp(){
if(selModels.length<2){alert('请至少选择2个模型');return}
var body=document.getElementById('cmpModalBody');
body.innerHTML='<table class="cmp-table"><thead><tr><th>项目</th>'
+selModels.map(function(m){return '<th>'+m.name+'</th>'}).join('')
+'</tr></thead><tbody>'
+'<tr><td>平台</td>'+selModels.map(function(m){return '<td>'+m.prov+'</td>'}).join('')+'</tr>'
+'<tr><td>输入价格</td>'+selModels.map(function(m){
var p=m.cur==='USD'?'$'+(m.inp*1e6).toFixed(4):'¥'+m.inp.toFixed(4);
return '<td>'+p+'/M</td>';
}).join('')+'</tr>'
+'<tr><td>输出价格</td>'+selModels.map(function(m){
var p=m.cur==='USD'?'$'+(m.out*1e6).toFixed(4):'¥'+m.out.toFixed(4);
return '<td>'+p+'/M</td>';
}).join('')+'</tr>'
+'<tr><td>上下文</td>'+selModels.map(function(m){return '<td>'+m.ctx+'</td>'}).join('')+'</tr>'
+'<tr><td>货币</td>'+selModels.map(function(m){return '<td>'+m.cur+'</td>'}).join('')+'</tr>'
+'</tbody></table>';
document.getElementById('cmpModal').style.display='flex';
}
function closeCmpModal(){document.getElementById('cmpModal').style.display='none'}

// ─── 月费计算器 ───
function getCalcParams(){
return {
chats:parseInt(document.getElementById('calcChats').value)||0,
tokens:parseInt(document.getElementById('calcTokens').value)||0,
ratio:parseFloat(document.getElementById('calcRatio').value)||1
};
}
function calcModelCost(m,params){
if(m.priceStatus!=='priced'&&m.priceStatus!=='free')return null;
var inTok=params.chats*params.tokens;
var outTok=inTok*params.ratio;
if(m.cur==="USD"){return (m.inp*inTok+m.out*outTok)*USD_TO_CNY;}
else{return m.inp*inTok/1e6+m.out*outTok/1e6;}
}
function runCalc(){
var params=getCalcParams();
var results=selModels.map(function(m){
return {name:m.name,cost:calcModelCost(m,params),cur:m.cur,inp:m.inp,out:m.out};
}).filter(function(r){return r.cost!==null;});
results.sort(function(a,b){return a.cost-b.cost});
if(results.length===0){
document.getElementById('calcResult').innerHTML='<div style="color:#94a3b8;font-size:13px;padding:10px">请先在上方勾选要计算的模型（最多3个）</div>';
return;
}
renderCalcResult(results,params);
}
function runCalcAll(){
var params=getCalcParams();
var cs=document.querySelectorAll('.mc');
var results=[];
cs.forEach(function(c){
if(c.style.display==='none')return;
var priceStatus=c.dataset.priceStatus||'unknown';
if(priceStatus!=='priced'&&priceStatus!=='free')return;
var mName=(c.querySelector('.mname')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var m={name:mName,inp:inp,out:out,cur:cur,priceStatus:priceStatus};
var cost=calcModelCost(m,params);
results.push({name:mName,cost:cost,cur:cur,inp:inp,out:out});
});
results.sort(function(a,b){return a.cost-b.cost});
if(results.length===0){
document.getElementById('calcResult').innerHTML='<div style="color:#94a3b8;font-size:13px;padding:10px">没有可计算的模型</div>';
return;
}
renderCalcResult(results.slice(0,30),params);
}
function runCalcReverse(){
var budget=parseFloat(document.getElementById('calcBudget').value)||0;
if(budget<=0){alert('请输入月预算金额');return;}
var params=getCalcParams();
if(params.chats<=0||params.tokens<=0){alert('请先设置对话次数和Token数');return;}
var cs=document.querySelectorAll('.mc');
var results=[];
cs.forEach(function(c){
if(c.style.display==='none')return;
var priceStatus=c.dataset.priceStatus||'unknown';
if(priceStatus!=='priced'&&priceStatus!=='free')return;
var mName=(c.querySelector('.mname')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var m={name:mName,inp:inp,out:out,cur:cur,priceStatus:priceStatus};
var cost=calcModelCost(m,params);
var maxChats=budget>0&&cost>0?Math.floor(budget/cost*params.chats):0;
results.push({name:mName,cost:cost,maxChats:maxChats,cur:cur});
});
results.sort(function(a,b){return b.maxChats-a.maxChats});
var html='<div class="calc-table-wrap"><table class="calc-table"><thead><tr><th>排名</th><th>模型</th><th>月费(¥)</th><th>预算内最多对话</th></tr></thead><tbody>';
results.slice(0,30).forEach(function(r,i){
var costStr='¥'+r.cost.toFixed(2);
html+='<tr><td>'+(i+1)+'</td><td>'+r.name+'</td><td>'+costStr+'</td><td><b>'+r.maxChats.toLocaleString()+'</b> 次</td></tr>';
});
html+='</tbody></table></div>';
document.getElementById('calcResult').innerHTML=html;
}
function renderCalcResult(results,params){
var html='<div class="calc-table-wrap"><table class="calc-table"><thead><tr><th>排名</th><th>模型</th><th>月费用(¥'+params.chats+'次×'+params.tokens+'T)</th></tr></thead><tbody>';
results.forEach(function(r,i){
var costStr='¥'+r.cost.toFixed(2);
html+='<tr><td>'+(i+1)+'</td><td>'+r.name+'</td><td><b>'+costStr+'</b></td></tr>';
});
html+='</tbody></table></div>';
document.getElementById('calcResult').innerHTML=html;
}

// ─── 智能推荐 ───
function runRecommend(scene){
var cs=document.querySelectorAll('.mc');
var results=[];
cs.forEach(function(c){
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var scen=c.dataset.s||'';
var ctx=parseInt(c.dataset.ctx)||0;
var tags=Array.from(c.querySelectorAll('.tg')).map(function(t){return t.textContent;});
var priceStatus=c.dataset.priceStatus||'unknown';
var score=0;
var reason='';
// 场景匹配评分
if(scene==='chat'){
if(scen==='日常对话')score+=30;
if(tags.indexOf('便宜')!==-1||tags.indexOf('极便宜')!==-1)score+=20;
if(tags.indexOf('免费额度')!==-1)score+=25;
if(inp>0&&inp<1)score+=15;
if(tags.indexOf('视觉')!==-1)score-=10; // 不需要视觉
if(inp>10)score-=20; // 太贵
reason=score>50?'性价比高，适合日常使用':'价格适中';
}else if(scene==='code'){
if(scen==='编程代码')score+=30;
if(tags.indexOf('代码')!==-1)score+=25;
if(tags.indexOf('推理')!==-1)score+=10;
if(ctx>=32000)score+=10;
if(tags.indexOf('视觉')!==-1)score-=5;
reason=tags.indexOf('代码')!==-1?'代码专用模型':'通用模型，可写代码';
}else if(scene==='translate'){
if(scen==='日常对话')score+=25;
if(inp>0&&inp<2)score+=20;
if(tags.indexOf('免费额度')!==-1)score+=25;
if(ctx>=32000)score+=10;
if(tags.indexOf('视觉')!==-1)score-=10;
reason='翻译不需要高级模型，便宜即可';
}else if(scene==='write'){
if(scen==='日常对话')score+=20;
if(scen==='深度推理')score+=15;
if(ctx>=64000)score+=15;
if(inp>0&&inp<5)score+=10;
reason=ctx>=64000?'长上下文，适合长文':'适合一般写作';
}else if(scene==='reason'){
if(scen==='深度推理')score+=30;
if(tags.indexOf('推理')!==-1)score+=25;
if(tags.indexOf('旗舰')!==-1)score+=10;
if(ctx>=128000)score+=10;
reason=tags.indexOf('推理')!==-1?'推理专用模型':'通用模型';
}else if(scene==='vision'){
if(scen==='视觉图片')score+=30;
if(tags.indexOf('视觉')!==-1)score+=25;
if(tags.indexOf('多模态')!==-1)score+=20;
reason='视觉/多模态模型';
}else if(scene==='image'){
if(scen==='图片生成')score+=30;
if(tags.indexOf('图片生成')!==-1)score+=25;
reason='图片生成专用';
}else if(scene==='video'){
if(scen==='视频生成')score+=30;
if(tags.indexOf('视频生成')!==-1)score+=25;
reason='视频生成专用';
}
// 通用加分
if(tags.indexOf('免费额度')!==-1)score+=5;
if(score>0)results.push({name:mName,prov:prov,score:score,inp:inp,out:out,cur:cur,reason:reason,priceStatus:priceStatus});
});
results.sort(function(a,b){return b.score-a.score});
var html='';
results.slice(0,5).forEach(function(r,i){
var price=r.priceStatus==='priced'?(r.cur==='USD'?'$'+(r.inp*1e6).toFixed(2)+'/M':'¥'+r.inp.toFixed(2)+'/M'):(r.priceStatus==='free'?'免费':'价格待确认');
html+='<div class="rec-card"><div class="rec-rank">'+(i+1)+'</div>'
+'<div class="rec-info"><div class="ri-name">'+r.name+'</div>'
+'<div class="ri-reason">'+r.prov+' · '+r.reason+'</div></div>'
+'<div class="rec-price">'+price+'</div></div>';
});
if(!html)html='<div style="color:#94a3b8;font-size:13px;padding:10px">未找到匹配模型</div>';
document.getElementById('recResult').innerHTML=html;
}

// ─── 跨平台比价 ───
// 精确的模型名标准化：提取模型系列+参数量+版本，用于跨平台匹配
function normalizeModelName(rawName){
var n=rawName;
// 去掉 OPENROUTER: 前缀
n=n.replace(/^OPENROUTER:/i,'');
// 去掉供应商前缀 (如 deepseek-ai/, Qwen/, Pro/ 等)
n=n.split('/').pop();
// 统一大小写用于匹配
var lower=n.toLowerCase();
// 提取模型系列名 + 参数量 + 关键版本标识
// DeepSeek 系列
if(lower.indexOf('deepseek')!==-1){
var v='';
if(/r1/i.test(n))v='R1';
else if(/v4/i.test(n)){
    if(/pro/i.test(n))v='V4-Pro';
    else if(/flash/i.test(n))v='V4-Flash';
    else v='V4';
}
else if(/v3\.2/i.test(n))v='V3.2';
else if(/v3\.1/i.test(n))v='V3.1';
else if(/v3/i.test(n))v='V3';
else if(/ocr/i.test(n))v='OCR';
else if(/chat/i.test(n))v='V4-Flash';
else if(/reasoner/i.test(n))v='V4-Flash';
else if(/prover/i.test(n))v='V4-Flash';
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var distill=/distill/i.test(n)?'-Distill':'';
var prover=/prover/i.test(n)?'-Prover':'';
return 'DeepSeek-'+v+distill+prover+(sz?'-'+sz:'');
}
// Qwen 系列
if(lower.indexOf('qwen')!==-1||lower.indexOf('qwq')!==-1){
var base=/qwq/i.test(n)?'QwQ':'Qwen';
var ver=(n.match(/(\d+\.\d+|\d+)/)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var vl=/vl/i.test(n)?'-VL':'';
var coder=/coder/i.test(n)?'-Coder':'';
var img=/image/i.test(n)?'-Image':'';
var think=/thinking/i.test(n)?'-Thinking':'';
var omni=/omni/i.test(n)?'-Omni':'';
var emb=/embedding/i.test(n)?'-Embedding':'';
return base+(ver?'-'+ver:'')+vl+coder+img+think+omni+emb+(sz?'-'+sz:'');
}
// GLM 系列
if(lower.indexOf('glm')!==-1){
var ver=(n.match(/glm[-_]?(\d+\.?\d*)/i)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var flash=/flash/i.test(n)?'-Flash':'';
var air=/air/i.test(n)?'-Air':'';
var turbo=/turbo/i.test(n)?'-Turbo':'';
var v=/v/i.test(n)&&/flash|air|turbo/i.test(n)===false?'-V':'';
var z=/z1/i.test(n)?'-Z1':'';
return 'GLM-'+ver+flash+air+turbo+v+z+(sz?'-'+sz:'');
}
// Kimi/Moonshot 系列
if(lower.indexOf('kimi')!==-1||lower.indexOf('moonshot')!==-1){
var v=/k2\.5/i.test(n)?'K2.5':/k2/i.test(n)?'K2':'V1';
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var ctx=(n.match(/(\d+k)/i)||['',''])[1].toLowerCase();
var think=/thinking/i.test(n)?'-Thinking':'';
var turbo=/turbo/i.test(n)?'-Turbo':'';
var vis=/vision/i.test(n)?'-Vision':'';
return 'Kimi-'+v+think+turbo+vis+(ctx?'-'+ctx:'')+(sz?'-'+sz:'');
}
// Doubao/豆包 系列
if(lower.indexOf('doubao')!==-1||lower.indexOf('seed')!==-1){
var v=(n.match(/(seed[-_]?\d+\.\d+|doubao[-_]?\d+\.\d+)/i)||['',''])[1]||'';
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var pro=/pro/i.test(n)?'-Pro':'';
var lite=/lite/i.test(n)?'-Lite':'';
var mini=/mini/i.test(n)?'-Mini':'';
var flash=/flash/i.test(n)?'-Flash':'';
var vis=/vision/i.test(n)?'-Vision':'';
var think=/thinking/i.test(n)?'-Thinking':'';
var coder=/coder/i.test(n)?'-Coder':'';
return 'Doubao-'+v+pro+lite+mini+flash+vis+think+coder+(sz?'-'+sz:'');
}
// Llama 系列
if(lower.indexOf('llama')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var guard=/guard/i.test(n)?'-Guard':'';
var chat=/chat/i.test(n)?'-Chat':'';
var instruct=/instruct/i.test(n)?'-Instruct':'';
return 'Llama-'+ver+guard+chat+instruct+(sz?'-'+sz:'');
}
// Mistral 系列
if(lower.indexOf('mistral')!==-1||lower.indexOf('mixtral')!==-1){
var base=/mixtral/i.test(n)?'Mixtral':'Mistral';
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var sz=(n.match(/(\d+b)/i)||['',''])[1].toUpperCase();
var small=/small/i.test(n)?'-Small':'';
var medium=/medium/i.test(n)?'-Medium':'';
var large=/large/i.test(n)?'-Large':'';
var nemo=/nemo/i.test(n)?'-Nemo':'';
var codestral=/codestral/i.test(n)?'-Codestral':'';
var pixtral=/pixtral/i.test(n)?'-Pixtral':'';
return base+(ver?'-'+ver:'')+small+medium+large+nemo+codestral+pixtral+(sz?'-'+sz:'');
}
// Claude 系列
if(lower.indexOf('claude')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var haiku=/haiku/i.test(n)?'-Haiku':'';
var sonnet=/sonnet/i.test(n)?'-Sonnet':'';
var opus=/opus/i.test(n)?'-Opus':'';
return 'Claude-'+ver+haiku+sonnet+opus;
}
// GPT 系列
if(lower.indexOf('gpt')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var turbo=/turbo/i.test(n)?'-Turbo':'';
var mini=/mini/i.test(n)?'-Mini':'';
var omni=/omni/i.test(n)?'-Omni':'';
var vis=/vision/i.test(n)?'-Vision':'';
return 'GPT-'+ver+turbo+mini+omni+vis;
}
// Gemini 系列
if(lower.indexOf('gemini')!==-1){
var ver=(n.match(/(\d+\.?\d*)/)||['',''])[1];
var flash=/flash/i.test(n)?'-Flash':'';
var pro=/pro/i.test(n)?'-Pro':'';
var think=/thinking/i.test(n)?'-Thinking':'';
return 'Gemini-'+ver+flash+pro+think;
}
// Yi/零一万物 系列
if(lower.indexOf('yi-')!==-1||lower.indexOf('yi ')!==-1){
var v=(n.match(/yi[-_](light|medium|large|spark|lightning|vision)/i)||['',''])[1]||'';
var turbo=/turbo/i.test(n)?'-Turbo':'';
return 'Yi-'+v.charAt(0).toUpperCase()+v.slice(1)+turbo;
}
// 通用的兜底：去掉常见后缀，保留核心名
var core=n.replace(/[-_](chat|instruct|fp\d+|latest|main|default|v\d+|it\d+|q\d+)/gi,'');
var sz2=(core.match(/(\d+b)/i)||['',''])[1].toUpperCase();
core=core.replace(/[-_]?\d+b/i,'');
return core+(sz2?'-'+sz2:'');
}

function buildCrossPrice(){
var cs=document.querySelectorAll('.mc');
var modelMap={};
var platformSet={};
cs.forEach(function(c){
var mName=(c.querySelector('.mname')||{}).textContent||'';
var prov=(c.querySelector('.prov')||{}).textContent||'';
var inp=parseFloat(c.dataset.inp)||0;
var out=parseFloat(c.dataset.out)||0;
var cur=c.dataset.cur||'CNY';
var pid=c.dataset.p||'';
// 精确标准化模型名
var coreName=normalizeModelName(mName);
if(!coreName)return;
if(!modelMap[coreName])modelMap[coreName]=[];
// 去重：同一平台同一模型只保留一个
var key=pid+'_'+coreName;
if(platformSet[key])return;
platformSet[key]=true;
modelMap[coreName].push({name:mName,prov:prov,inp:inp,out:out,cur:cur,baseName:coreName,pid:pid,isProxy:pid==='n1n'||pid==='ca'});
});
// 搜索过滤
var crossQ=(document.getElementById('crossSearchInput')||{}).value||'';
crossQ=crossQ.trim().toLowerCase();
// 只显示在2个以上不同平台出现的模型
var groups=Object.values(modelMap).filter(function(g){
var pids={};g.forEach(function(m){pids[m.pid]=1;});
var ok=Object.keys(pids).length>=2&&g.length<=15;
if(ok&&crossQ){ok=g[0].baseName.toLowerCase().indexOf(crossQ)!==-1;}
return ok;
});
// 按平台数排序，平台数相同按最低价排序
groups.sort(function(a,b){
var pa={};a.forEach(function(m){pa[m.pid]=1;});
var pb={};b.forEach(function(m){pb[m.pid]=1;});
var da=Object.keys(pa).length,db=Object.keys(pb).length;
if(da!==db)return db-da;
var minA=Infinity,minB=Infinity;
a.forEach(function(m){var c=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;if(c<minA)minA=c;});
b.forEach(function(m){var c=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;if(c<minB)minB=c;});
return minA-minB;
});
var html='';
groups.forEach(function(g){
// 找最低价
var minCost=Infinity;
g.forEach(function(m){
var cnyInp=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;
if(cnyInp<minCost)minCost=cnyInp;
});
// 统计平台数
var pids={};g.forEach(function(m){pids[m.pid]=1;});
var pCount=Object.keys(pids).length;
html+='<div class="cross-group"><div class="cross-group-name">'+g[0].baseName+' ('+pCount+'个平台, '+g.length+'个渠道)</div>';
// 按价格排序
var sorted=g.slice().sort(function(a,b){
var ca=a.cur==='USD'?a.inp*1e6*USD_TO_CNY:a.inp;
var cb=b.cur==='USD'?b.inp*1e6*USD_TO_CNY:b.inp;
return ca-cb;
});
sorted.forEach(function(m){
var cnyInp=m.cur==='USD'?m.inp*1e6*USD_TO_CNY:m.inp;
var priceStr=m.cur==="USD"?"$"+(m.inp*1e6).toFixed(2)+"/M":"\u00a5"+m.inp.toFixed(2)+"/M";
if(m.inp===0&&m.out===0)priceStr="\u514d\u8d39";
var isBest=Math.abs(cnyInp-minCost)<0.01;
var diff=cnyInp-minCost;
var diffStr="";
if(diff>0.01&&minCost>0)diffStr=" <span style=\"color:#94a3b8;font-size:10px\">(+"+((diff/minCost)*100).toFixed(0)+"%)</span>";
var proxyTag=m.isProxy?'<span style="color:#f97316;font-size:9px;font-weight:700;margin-left:2px" title="代理平台自营价,非官方价">P</span>':"";
html+="<div class=\"cross-item\"><span class=\"cross-platform\">"+m.prov+"</span>"
+"<span class=\"cross-price\">"+priceStr+"</span>"
+(isBest?"<span class=\"cross-best\">\u6700\u4f4e</span>":"")
+diffStr+proxyTag
+"</div>";
});
html+="</div>";
});
if(html){
document.getElementById("crossPanel").style.display="block";
document.getElementById("crossList").innerHTML=html;
}else{
document.getElementById("crossPanel").style.display="block";
document.getElementById("crossList").innerHTML='<div style="padding:8px;font-size:12px;color:var(--text3)">未找到匹配的跨平台模型</div>';
}
}


// ─── 代码片段模态框 ───
var _codeModalData = null;
function showCodeModal(baseUrl, modelName, platformId){
var modal = document.getElementById('codeModal');
if(!modal) return;
// 从 base_url 提取 base_url (去掉 /chat/completions 后缀)
var apiBase = baseUrl.replace(/\/chat\/completions\/?$/,'');
_codeModalData = {baseUrl:baseUrl, apiBase:apiBase, model:modelName, platform:platformId};
// 更新标题
var titleEl = modal.querySelector('.cm-model');
if(titleEl) titleEl.textContent = modelName;
// 默认显示 Python
switchCodeTab('python');
modal.classList.add('show');
}
function closeCodeModal(){
var modal = document.getElementById('codeModal');
if(modal) modal.classList.remove('show');
}
function switchCodeTab(lang){
if(!_codeModalData) return;
var d = _codeModalData;
document.querySelectorAll('.code-tab').forEach(function(t){t.classList.remove('active');});
var tab = document.querySelector('.code-tab[data-lang="'+lang+'"]');
if(tab) tab.classList.add('active');
var code = '';
if(lang === 'python'){
code = 'from openai import OpenAI\n\nclient = OpenAI(\n    api_key="YOUR_API_KEY",\n    base_url="'+d.apiBase+'"\n)\n\nresponse = client.chat.completions.create(\n    model="'+d.model+'",\n    messages=[\n        {"role": "system", "content": "You are a helpful assistant."},\n        {"role": "user", "content": "Hello!"}\n    ]\n)\n\nprint(response.choices[0].message.content)';
}else if(lang === 'nodejs'){
code = 'import OpenAI from "openai";\n\nconst client = new OpenAI({\n    apiKey: "YOUR_API_KEY",\n    baseURL: "'+d.apiBase+'"\n});\n\nconst response = await client.chat.completions.create({\n    model: "'+d.model+'",\n    messages: [\n        { role: "system", content: "You are a helpful assistant." },\n        { role: "user", content: "Hello!" }\n    ]\n});\n\nconsole.log(response.choices[0].message.content);';
}else if(lang === 'curl'){
code = 'curl '+d.baseUrl+' \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -d \'{\n    "model": "'+d.model+'",\n    "messages": [\n      {"role": "system", "content": "You are a helpful assistant."},\n      {"role": "user", "content": "Hello!"}\n    ]\n  }\'';
}else if(lang === 'stream'){
code = 'from openai import OpenAI\n\nclient = OpenAI(\n    api_key="YOUR_API_KEY",\n    base_url="'+d.apiBase+'"\n)\n\nstream = client.chat.completions.create(\n    model="'+d.model+'",\n    messages=[\n        {"role": "user", "content": "Hello!"}\n    ],\n    stream=True\n)\n\nfor chunk in stream:\n    if chunk.choices[0].delta.content:\n        print(chunk.choices[0].delta.content, end="")';
}
var block = document.getElementById('codeBlock');
if(block){
block.querySelector('pre').textContent = code;
var copyBtn = block.querySelector('.code-copy-btn');
if(copyBtn){copyBtn.classList.remove('copied');copyBtn.textContent='复制';}
}
}
function copyCodeBlock(){
var block = document.getElementById('codeBlock');
if(!block) return;
var code = block.querySelector('pre').textContent;
var btn = block.querySelector('.code-copy-btn');
if(navigator.clipboard && navigator.clipboard.writeText){
navigator.clipboard.writeText(code).then(function(){
if(btn){btn.classList.add('copied');btn.textContent='已复制';}
setTimeout(function(){if(btn){btn.classList.remove('copied');btn.textContent='复制';}},2000);
});
}else{
fallbackCopy(code);
if(btn){btn.classList.add('copied');btn.textContent='已复制';}
setTimeout(function(){if(btn){btn.classList.remove('copied');btn.textContent='复制';}},2000);
}
}

// ─── 复制命令 ───
function copyCmd(cmd,name){
function showTip(msg,ok){
var t=document.getElementById("toast");
t.innerHTML=(ok?"<span style=\"margin-right:6px\">\u2713</span>":"")+msg;
t.className="toast-show"+(ok?" toast-ok":" toast-err");
clearTimeout(t._tid);
t._tid=setTimeout(function(){t.className="";},2800);
}
if(navigator.clipboard&&navigator.clipboard.writeText){
navigator.clipboard.writeText(cmd).then(function(){
showTip("\u5df2\u590d\u5236: "+cmd.substring(0,60),true);
}).catch(function(){
fallbackCopy(cmd);showTip("\u5df2\u590d\u5236: "+cmd.substring(0,60),true);
});
}else{
fallbackCopy(cmd);showTip("\u5df2\u590d\u5236: "+cmd.substring(0,60),true);
}
}
function fallbackCopy(text){
var ta=document.createElement("textarea");ta.value=text;ta.style.cssText="position:fixed;left:-9999px";
document.body.appendChild(ta);ta.select();
try{document.execCommand("copy");}catch(e){}
document.body.removeChild(ta);
}

// ─── 状态持久化 ───
function saveState(){
var state={p:curP,s:curS,pt:curPT,sort:curSort,tags:curTags,ctx:curCtx,family:curFamily,
q:(document.getElementById('si').value||'')};
window.location.hash=encodeURIComponent(JSON.stringify(state));
}
function restoreState(){
try{
var hash=window.location.hash.substring(1);
if(!hash)return;
var state=JSON.parse(decodeURIComponent(hash));
if(state.p){curP=state.p;var pb=document.querySelector('.pt[data-p="'+state.p+'"]');if(pb){document.querySelectorAll('.pt').forEach(function(x){x.classList.remove('active')});pb.classList.add('active');}}
if(state.s){curS=state.s;var sb=document.querySelector('.sc[data-sc="'+state.s+'"]');if(sb){document.querySelectorAll('.sc').forEach(function(x){x.classList.remove('active')});sb.classList.add('active');}}
if(state.pt){curPT=state.pt;var ptb=document.querySelector('.pt-filter[data-pt="'+state.pt+'"]');if(ptb){document.querySelectorAll('.pt-filter').forEach(function(x){x.classList.remove('active')});ptb.classList.add('active');}}
if(state.sort){curSort=state.sort;var sob=document.querySelector('.sort-btn[data-sort="'+state.sort+'"]');if(sob){document.querySelectorAll('.sort-btn').forEach(function(x){x.classList.remove('active')});sob.classList.add('active');}}
if(state.tags&&state.tags.length>0){curTags=state.tags;state.tags.forEach(function(t){var tb=document.querySelector('.tag-btn[data-tag="'+t+'"]');if(tb)tb.classList.add('active');});}
if(state.ctx){curCtx=state.ctx;var cb=document.querySelector('.ctx-btn[data-ctx="'+state.ctx+'"]');if(cb){document.querySelectorAll('.ctx-btn').forEach(function(x){x.classList.remove('active')});cb.classList.add('active');}}
if(state.family){curFamily=state.family;var fb=document.querySelector('.family-btn[data-family="'+state.family+'"]');if(fb){document.querySelectorAll('.family-btn').forEach(function(x){x.classList.remove('active')});fb.classList.add('active');}}
if(state.q){document.getElementById('si').value=state.q;}
}catch(e){}
}


// ═══════════════════════════════════════════════════════════
// 真实文本计价器
// ═══════════════════════════════════════════════════════════
function showTokenCalc(){
    var m=document.getElementById('tkModal');
    if(m)m.classList.add('show');
}
function closeTokenCalc(){
    var m=document.getElementById('tkModal');
    if(m)m.classList.remove('show');
}

// GPT-4 Cl100k 近似分词器
function estimateTokens(text){
    if(!text)return 0;
    var len=text.length;
    var cjk=0;
    for(var i=0;i<len;i++){
        var c=text.charCodeAt(i);
        if((c>=0x4E00&&c<=0x9FFF)||(c>=0x3400&&c<=0x4DBF)||(c>=0x3000&&c<=0x303F)||(c>=0xFF00&&c<=0xFFEF))cjk++;
    }
    var nonCjk=len-cjk;
    return Math.ceil(nonCjk/4+cjk/1.5);
}

function calcTokens(){
    var text=document.getElementById('tkText').value;
    if(!text.trim()){showTip('请先输入文本',false);return;}
    var tokens=estimateTokens(text);
    var chars=text.length;
    var lines=text.split('\n').length;
    var estOutTokens=Math.round(tokens*0.4);

    var statsHtml='<div class="tk-stat"><div class="tk-stat-label">字符数</div><div class="tk-stat-value">'+chars.toLocaleString()+'</div></div>'
        +'<div class="tk-stat"><div class="tk-stat-label">行数</div><div class="tk-stat-value">'+lines.toLocaleString()+'</div></div>'
        +'<div class="tk-stat"><div class="tk-stat-label">输入 Token</div><div class="tk-stat-value">~'+tokens.toLocaleString()+'</div></div>'
        +'<div class="tk-stat"><div class="tk-stat-label">预估输出 Token</div><div class="tk-stat-value">~'+estOutTokens.toLocaleString()+'</div></div>';
    document.getElementById('tkStats').innerHTML=statsHtml;

    var cs=document.querySelectorAll('.mc');
    var results=[];
    cs.forEach(function(c){
        var inp=parseFloat(c.dataset.inp)||0;
        var out=parseFloat(c.dataset.out)||0;
        var cur=c.dataset.cur||'CNY';
        var pid=c.dataset.p||'';
        var mname=(c.querySelector('.mname')||{}).textContent||'';
        var pname=(c.querySelector('.prov')||{}).textContent||'';
        if(inp===0&&out===0)return;
        var pu=c.dataset.pu||'per_token';
        var cost;
        if(cur==='CNY'){
            cost=(inp*tokens+out*estOutTokens)/1e6;
        }else{
            var mul=pu==='per_1m'?1e-6:1;
            cost=(inp*tokens+out*estOutTokens)*mul;
        }
        results.push({pid:pid,mname:mname,pname:pname,cost:cost,cur:cur});
    });

    results.sort(function(a,b){return a.cost-b.cost;});
    var minCost=results.length>0?results[0].cost:0;

    var html='<table class="tk-result-table"><tr><th>#</th><th>平台</th><th>模型</th><th>预估花费</th></tr>';
    var shown=0;
    for(var i=0;i<results.length&&shown<30;i++){
        var r=results[i];
        var costStr;
        if(r.cur==='CNY')costStr='¥'+r.cost.toFixed(4);
        else costStr='$'+r.cost.toFixed(4);
        var cheapest=r.cost===minCost?'tk-cheapest':'';
        html+='<tr><td>'+(i+1)+'</td><td>'+r.pname+'</td><td class="'+cheapest+'">'+r.mname+'</td><td class="'+cheapest+'">'+costStr+'</td></tr>';
        shown++;
    }
    html+='</table>';
    if(results.length>30)html+='<div style="font-size:10px;color:var(--text3);margin-top:4px">显示前30个最便宜的，共'+results.length+'个模型</div>';
    document.getElementById('tkResult').innerHTML=html;
}

function clearTokenCalc(){
    document.getElementById('tkText').value='';
    document.getElementById('tkStats').innerHTML='';
    document.getElementById('tkResult').innerHTML='';
}

// ═══════════════════════════════════════════════════════════
// TTFB 测速（搜索模型名 → 自动测所有平台）
// ═══════════════════════════════════════════════════════════
var pingSelectedModel='';

function showPingModal(){
    var m=document.getElementById('pingModal');
    if(m)m.classList.add('show');
}
function closePingModal(){
    var m=document.getElementById('pingModal');
    if(m)m.classList.remove('show');
}

function updatePingSuggestions(){
    var q=(document.getElementById('pingModelInput').value||'').toLowerCase().trim();
    var div=document.getElementById('pingSuggestions');
    if(!q||q.length<2){div.innerHTML='';return;}
    // 收集所有匹配的模型名（去重）
    var cs=document.querySelectorAll('.mc');
    var modelNames=[];
    var seenName={};
    cs.forEach(function(c){
        var mname=(c.querySelector('.mname')||{}).textContent||'';
        var key=mname.toLowerCase();
        if(seenName[key])return;
        if(key.indexOf(q)===-1)return;
        seenName[key]=1;
        // 统计该模型在多少个平台可用
        var platformCount=0;
        cs.forEach(function(c2){
            var n2=(c2.querySelector('.mname')||{}).textContent||'';
            if(n2===mname)platformCount++;
        });
        modelNames.push({name:mname,count:platformCount});
    });
    modelNames.sort(function(a,b){return b.count-a.count;});
    var html='';
    var count=0;
    modelNames.forEach(function(item){
        if(count>=10)return;
        html+='<div style="display:inline-block;padding:3px 8px;margin:2px;border-radius:6px;border:1px solid var(--border);font-size:10px;cursor:pointer;background:var(--surface2);color:var(--text)" onclick="selectPingModel(\''+item.name.replace(/'/g,"\\'")+'\')">'+item.name+' <span style="color:var(--text3)">('+item.count+'平台)</span></div>';
        count++;
    });
    div.innerHTML=html||'<span style="font-size:10px;color:var(--text3)">未找到匹配模型</span>';
}

function selectPingModel(name){
    pingSelectedModel=name;
    document.getElementById('pingModelInput').value=name;
    document.getElementById('pingSuggestions').innerHTML='';
}

function startPing(){
    if(!pingSelectedModel){showTip('请先输入模型名',false);return;}
    // 收集所有平台中该模型的接口
    var cs=document.querySelectorAll('.mc');
    var endpoints=[];
    var seen={};
    cs.forEach(function(c){
        var mname=(c.querySelector('.mname')||{}).textContent||'';
        if(mname!==pingSelectedModel)return;
        var pname=(c.querySelector('.prov')||{}).textContent||'';
        var baseUrl=(c.querySelector('.base-url')||{}).textContent||'';
        var key=pname+baseUrl;
        if(seen[key])return;
        seen[key]=1;
        endpoints.push({pname:pname,baseUrl:baseUrl});
    });

    if(endpoints.length===0){showTip('未找到该模型的接口',false);return;}

    var btn=document.getElementById('pingStartBtn');
    btn.disabled=true;
    btn.innerHTML='<span class="ping-spinner"></span>测速中...';

    var listDiv=document.getElementById('pingResultList');
    listDiv.innerHTML='<div style="font-size:11px;color:var(--text3)">正在测试 '+endpoints.length+' 个平台的 '+pingSelectedModel+'...</div>';

    var results=[];
    var done=0;
    var total=endpoints.length;

    endpoints.forEach(function(ep,idx){
        var url=ep.baseUrl;
        var body=JSON.stringify({model:pingSelectedModel,messages:[{role:"user",content:"hi"}],max_tokens:1});
        var start=performance.now();
        var timeoutId;

        var controller=new AbortController();
        timeoutId=setTimeout(function(){controller.abort();},8000);

        fetch(url,{
            method:'POST',
            headers:{'Content-Type':'application/json','Authorization':'Bearer pk-test'},
            body:body,
            signal:controller.signal
        }).then(function(resp){
            clearTimeout(timeoutId);
            var ttfb=Math.round(performance.now()-start);
            // 401/403/429: TTFB仍然有效（网络通了，只是认证失败）
            var st=(resp.status>=200&&resp.status<300)||resp.status===401||resp.status===403||resp.status===429||resp.status===400?'ok':'error';
            results.push({pname:ep.pname,ms:ttfb,status:st});
        }).catch(function(err){
            clearTimeout(timeoutId);
            var ttfb=Math.round(performance.now()-start);
            if(err.name==='AbortError'){
                results.push({pname:ep.pname,ms:-1,status:'timeout'});
            }else{
                results.push({pname:ep.pname,ms:ttfb,status:'error'});
            }
        }).finally(function(){
            done++;
            if(done===total){
                renderPingResults(results);
                btn.disabled=false;
                btn.innerHTML='开始测速';
            }else{
                listDiv.innerHTML='<div style="font-size:11px;color:var(--text3)">已测试 '+done+'/'+total+'...</div>';
            }
        });
    });
}

function renderPingResults(results){
    results.sort(function(a,b){
        if(a.status!=='ok'&&b.status==='ok')return 1;
        if(a.status==='ok'&&b.status!=='ok')return -1;
        return a.ms-b.ms;
    });

    var maxMs=0;
    results.forEach(function(r){if(r.ms>0&&r.ms>maxMs)maxMs=r.ms;});
    if(maxMs===0)maxMs=1000;

    var html='';
    results.forEach(function(r,i){
        var msClass='ping-ms-mid';
        var barColor='#eab308';
        var barW=0;
        if(r.status==='ok'){
            if(r.ms<500){msClass='ping-ms-fast';barColor='#22c55e';}
            else if(r.ms>2000){msClass='ping-ms-slow';barColor='#ef4444';}
            barW=Math.min(100,(r.ms/maxMs)*100);
        }
        html+='<div class="ping-result-item">'
            +'<span class="ping-platform">'+r.pname+'</span>';
        if(r.status==='ok'){
            html+='<span class="ping-ms '+msClass+'">'+r.ms+'ms</span>';
        }else if(r.status==='timeout'){
            html+='<span class="ping-ms ping-ms-timeout">超时</span>';
        }else{
            html+='<span class="ping-ms ping-ms-timeout">错误</span>';
        }
        html+='<div class="ping-bar-wrap"><div class="ping-bar" style="width:'+barW+'%;background:'+barColor+'"></div></div>';
        if(i===0&&r.status==='ok')html+='<span style="font-size:9px;color:#22c55e;font-weight:700">最快</span>';
        else html+='<span style="font-size:9px;color:var(--text3)">'+(i+1)+'</span>';
        html+='</div>';
    });

    document.getElementById('pingResultList').innerHTML=html;
}

function clearPingResult(){
    document.getElementById('pingResultList').innerHTML='';
    pingSelectedModel='';
    pingBaseUrl='';
    document.getElementById('pingModelInput').value='';
    document.getElementById('pingSuggestions').innerHTML='';
}


function toggleFg(el){
    var fg=el.parentElement;
    fg.classList.toggle('fg-collapsed');
    var arrow=el.querySelector('.fg-arrow');
    if(fg.classList.contains('fg-collapsed')){arrow.textContent='▸';}
    else{arrow.textContent='▾';}
}
function clearAllFilters(){
    document.getElementById('si').value='';
    document.querySelectorAll('.pt.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.pt')[0].classList.add('active');
    document.querySelectorAll('.pt-filter.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.pt-filter')[0].classList.add('active');
    document.querySelectorAll('.sc.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.sc')[0].classList.add('active');
    document.querySelectorAll('.family-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.family-btn')[0].classList.add('active');
    document.querySelectorAll('.tag-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.ctx-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.ctx-btn')[0].classList.add('active');
    document.querySelectorAll('.sort-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.sort-btn')[0].classList.add('active');
    document.querySelectorAll('.cur-btn.active').forEach(function(b){b.classList.remove('active')});
    document.querySelectorAll('.cur-btn')[0].classList.add('active');
    curP='all';curPT='all';curS='all';curFamily='all';curCtx='all';curSort='default';curTags=[];curCur='CNY';
    var pm=document.getElementById('priceMin');if(pm)pm.value='';
    var px=document.getElementById('priceMax');if(px)px.value='';
    filter();updatePrices();
}
function toggleSidebar(){
    var sb=document.getElementById('sidebar');
    if(sb)sb.classList.toggle('open');
}
