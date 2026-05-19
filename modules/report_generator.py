from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# ── Language icon map ─────────────────────────────────────────────────────────
_LANG_ICONS = {
    "python": "🐍", "javascript": "🟨", "typescript": "🔷", "java": "☕",
    "go": "🐹", "rust": "🦀", "cpp": "⚙️", "c": "⚙️", "ruby": "💎",
    "php": "🐘", "swift": "🐦", "kotlin": "🎯", "scala": "♾️",
    "html": "🌐", "css": "🎨", "scss": "🎨", "sql": "🗃️",
    "shell": "🖥️", "bash": "🖥️", "json": "📋", "yaml": "📋",
    "markdown": "📝", "text": "📄",
}

# ── Flat light CSS (Element Plus design tokens) ───────────────────────────────
_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
     background:#f5f7fa;color:#303133;font-size:14px;line-height:1.6}
.page{max-width:920px;margin:0 auto;padding:24px 18px 60px}
/* ── Toolbar ── */
.toolbar{position:sticky;top:0;z-index:10;background:#fff;border:1px solid #e4e7ed;
         border-radius:8px;padding:12px 18px;margin-bottom:16px;
         display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;
         box-shadow:0 1px 4px rgba(0,0,0,.06)}
.toolbar-brand{display:flex;align-items:center;gap:8px}
.toolbar-brand-icon{width:22px;height:22px;border-radius:5px;
                    background:linear-gradient(135deg,#409eff,#67c23a);
                    display:grid;place-items:center;font-size:11px;color:#fff;flex-shrink:0}
.toolbar-title{font-size:15px;font-weight:700;color:#303133}
.toolbar-sub{font-size:12px;color:#909399;margin-top:1px}
.toolbar-right{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.ai-cfg-row{display:flex;flex-wrap:wrap;gap:5px;align-items:center;font-size:12px;color:#909399}
.ai-cfg-row select,.ai-cfg-row input{border:1px solid #dcdfe6;border-radius:4px;padding:4px 8px;
   font:inherit;font-size:12px;background:#fff;color:#303133;outline:none;
   transition:border-color .2s}
.ai-cfg-row select:focus,.ai-cfg-row input:focus{border-color:#409eff}
.btn{display:inline-flex;align-items:center;gap:4px;border-radius:4px;font:inherit;
     font-size:12px;font-weight:500;cursor:pointer;white-space:nowrap;transition:all .2s;padding:5px 10px}
.btn-default{background:#fff;border:1px solid #dcdfe6;color:#606266}
.btn-default:hover{color:#409eff;border-color:#c6e2ff;background:#ecf5ff}
.btn-primary{background:#409eff;border:1px solid #409eff;color:#fff}
.btn-primary:hover{background:#79bbff;border-color:#79bbff}
.status-dot{width:8px;height:8px;border-radius:50%;background:#dcdfe6;display:inline-block;transition:background .3s}
.status-dot.ok{background:#67c23a;box-shadow:0 0 0 3px rgba(103,194,58,.2)}
/* ── Cards ── */
.card{background:#fff;border:1px solid #e4e7ed;border-radius:8px;padding:18px 20px;margin-bottom:14px}
.card-title{font-size:12px;font-weight:600;color:#909399;text-transform:uppercase;
            letter-spacing:.06em;margin-bottom:14px;display:flex;align-items:center;gap:6px}
/* ── Git bar ── */
.git-bar{background:#fff;border:1px solid #e4e7ed;border-radius:8px;padding:10px 16px;
         margin-bottom:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:12px}
.git-chip{display:inline-flex;align-items:center;gap:4px;background:#ecf5ff;color:#409eff;
          border:1px solid #d9ecff;border-radius:4px;padding:2px 8px;font-weight:500}
.git-chip.mono{font-family:monospace;font-size:11px}
.git-chip.muted{background:#f4f4f5;color:#909399;border-color:#e9e9eb}
.git-msg{color:#606266;font-style:italic;overflow:hidden;text-overflow:ellipsis;
         white-space:nowrap;flex:1;min-width:0}
.git-meta{color:#c0c4cc;white-space:nowrap}
/* ── Stats row ── */
.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px}
.stat-card{background:#fff;border:1px solid #e4e7ed;border-radius:8px;padding:14px 16px}
.stat-label{font-size:11px;color:#909399;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px}
.stat-value{font-size:22px;font-weight:700;color:#303133}
.stat-value.green{color:#67c23a}
.stat-value.red{color:#f56c6c}
/* ── Section title ── */
.section-title{font-size:13px;font-weight:600;color:#606266;margin-bottom:10px;
               display:flex;align-items:center;gap:6px}
/* ── Log ── */
.terminal-log{max-height:360px;overflow:auto;background:#1e1e1e;color:#d4d4d4;
              border-radius:6px;padding:14px;white-space:pre-wrap;
              font-family:'SF Mono','Fira Code',monospace;font-size:12px;line-height:1.55}
/* ── AI Summary ── */
.ai-summary-text{color:#606266;font-size:13.5px;line-height:1.75}
/* ── Change cards (compact) ── */
.change-card{background:#fff;border:1px solid #e4e7ed;border-radius:8px;padding:12px 16px;
             margin-bottom:8px;display:flex;align-items:center;gap:12px;
             transition:border-color .2s,box-shadow .2s;cursor:pointer;user-select:none}
.change-card:hover{border-color:#a0cfff;box-shadow:0 2px 8px rgba(64,158,255,.12)}.change-card.accepted{border-left:3px solid #67c23a}
.change-card.rejected{border-left:3px solid #f56c6c}
.lang-icon{font-size:20px;flex-shrink:0;line-height:1}
.change-card-info{flex:1;min-width:0}
.file-path{font-family:'SF Mono','Fira Code',Menlo,monospace;font-size:13px;font-weight:600;
           color:#303133;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card-tags{display:flex;gap:5px;margin-top:4px;flex-wrap:wrap}
.tag-chip{font-size:11px;padding:1px 7px;border-radius:3px;font-weight:500;
          background:#f4f4f5;color:#909399;border:1px solid #e9e9eb}
.tag-chip.modified{background:#fdf6ec;color:#e6a23c;border-color:#faecd8}
.tag-chip.added,.tag-chip.created{background:#f0f9eb;color:#67c23a;border-color:#c2e7b0}
.tag-chip.deleted{background:#fef0f0;color:#f56c6c;border-color:#fbc4c4}
.change-card-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.status-badge{font-size:11px;padding:2px 8px;border-radius:3px;font-weight:500;display:none}
.status-badge.accepted{display:inline;background:#f0f9eb;color:#67c23a;border:1px solid #c2e7b0}
.status-badge.rejected{display:inline;background:#fef0f0;color:#f56c6c;border:1px solid #fbc4c4}
.btn-analyze{display:inline-flex;align-items:center;gap:5px;background:#409eff;
             color:#fff;border:none;border-radius:4px;padding:6px 14px;
             font-size:12px;font-weight:500;cursor:pointer;transition:background .2s;white-space:nowrap}
.btn-analyze:hover{background:#79bbff}
.btn-analyze:active{background:#337ecc}
/* ── Dialog (Element Plus el-dialog overrides) ── */
.th-ai-dialog .el-dialog{border-radius:8px}
.th-ai-dialog .el-dialog__header{padding:16px 20px 12px;border-bottom:1px solid #e4e7ed}
.th-ai-dialog .el-dialog__title{font-size:14px;font-weight:600;color:#303133;
                                 font-family:'SF Mono','Fira Code',monospace}
.th-ai-dialog .el-dialog__body{padding:0;max-height:calc(88vh - 140px);overflow-y:auto}
.th-ai-dialog .el-dialog__footer{border-top:1px solid #e4e7ed;padding:12px 20px}
.th-ai-dialog .el-tabs__header{padding:0 20px;margin:0}
.th-ai-dialog .el-tabs__content{padding:16px 20px}
.dialog-footer{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
/* ── Diff in dialog ── */
.diff-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.diff-pane-label{font-size:11px;font-weight:600;color:#909399;text-transform:uppercase;
                 letter-spacing:.05em;margin-bottom:6px}
.code-pre{background:#f6f8fa;border:1px solid #e4e7ed;border-radius:6px;padding:12px;
          font-family:'SF Mono','Fira Code',Menlo,monospace;font-size:12px;line-height:1.6;
          max-height:300px;overflow-x:auto;overflow-y:auto;white-space:pre;word-break:normal;
          overscroll-behavior:contain;display:block}
/* ensure hljs tokens inside .code-pre render at correct size */
.code-pre .hljs,.code-pre.hljs{background:transparent;padding:0}
.diff-rendered{border:1px solid #e4e7ed;border-radius:6px;overflow:hidden;
               font-family:monospace;font-size:12px}
.diff-rendered>div{padding:3px 10px;white-space:pre-wrap;line-height:1.5}
.diff-file{background:#e8f4fd;color:#409eff}
.diff-hunk{background:#f3e8ff;color:#9c59d1}
.diff-add{background:#f0f9eb;color:#4a9e37}
.diff-remove{background:#fef0f0;color:#c0392b}
/* ── AI content in dialog ── */
.ai-progress-text{font-size:12px;color:#909399;font-family:monospace;white-space:pre-wrap;
                  max-height:90px;overflow-y:auto;border:1px solid #e4e7ed;border-radius:4px;
                  padding:8px 10px;background:#fafafa;margin-bottom:10px;line-height:1.5}
.ai-thinking-box{background:#fdf6ec;border:1px solid #faecd8;border-radius:6px;
                 padding:10px 12px;margin-bottom:10px}
.ai-thinking-label{font-size:11px;font-weight:600;color:#e6a23c;margin-bottom:5px}
.ai-thinking-text{font-size:11.5px;color:#b07d2e;white-space:pre-wrap;
                  max-height:100px;overflow-y:auto;font-family:monospace}
.ai-result-box{border:1px solid #e4e7ed;border-radius:6px;padding:14px 16px;
               background:#fff;min-height:80px;font-size:13.5px;line-height:1.75;color:#303133}
.ai-result-box h1,.ai-result-box h2,.ai-result-box h3{font-size:14px;font-weight:600;
  margin:12px 0 5px;color:#303133}
.ai-result-box p{margin:5px 0;color:#606266}
.ai-result-box ul,.ai-result-box ol{padding-left:20px;margin:5px 0}
.ai-result-box li{margin:2px 0;color:#606266}
.ai-result-box code{background:#f4f4f5;color:#e6a23c;border-radius:3px;padding:1px 5px;
                    font-family:monospace;font-size:12px}
.ai-result-box pre{background:#f5f7fa;border:1px solid #e4e7ed;border-radius:6px;
                   margin:8px 0;overflow-x:auto}
.ai-result-box pre code{background:none;color:#303133;padding:10px;display:block;font-size:12px}
.ai-result-box blockquote{border-left:3px solid #409eff;margin:5px 0;padding:4px 12px;
                          color:#909399;border-radius:0 4px 4px 0}
/* ── Footer ── */
.footer{text-align:center;color:#c0c4cc;padding:20px 0;font-size:12px}
@media(max-width:720px){.diff-grid{grid-template-columns:1fr}}
@media print{.toolbar{position:static;box-shadow:none}.btn-analyze,.toolbar-right{display:none!important}}
"""

# ── Vue 3 + Element Plus app (not an f-string — uses {{ }} freely) ────────────
_VUE_SCRIPT = r"""
<script>
const { createApp, ref, reactive, computed, nextTick } = Vue;

const _LANG_ICONS = {
  python:'🐍',javascript:'🟨',typescript:'🔷',java:'☕',go:'🐹',rust:'🦀',
  cpp:'⚙️',c:'⚙️',ruby:'💎',php:'🐘',swift:'🐦',kotlin:'🎯',
  html:'🌐',css:'🎨',scss:'🎨',sql:'🗃️',shell:'🖥️',bash:'🖥️',
  json:'📋',yaml:'📋',markdown:'��',text:'📄'
};
function langIcon(l){ return _LANG_ICONS[(l||'').toLowerCase()]||'📄'; }

function renderMd(md){
  if(typeof marked!=='undefined') return marked.parse(md||'');
  const p=document.createElement('pre');p.style.cssText='white-space:pre-wrap;margin:0';
  p.textContent=md||'';return p.outerHTML;
}
function api(path){ return window.location.origin+path; }

function _esc(s){ return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function _ext2lang(fp){
  const ext=(fp||'').split('.').pop().toLowerCase();
  return({js:'javascript',ts:'typescript',tsx:'typescript',jsx:'javascript',
    py:'python',rb:'ruby',go:'go',rs:'rust',java:'java',swift:'swift',
    kt:'kotlin',cpp:'cpp',cc:'cpp',cxx:'cpp',c:'c',h:'c',
    php:'php',cs:'csharp',css:'css',scss:'scss',less:'css',
    html:'html',htm:'html',xml:'xml',sh:'bash',bash:'bash',zsh:'bash',
    sql:'sql',json:'json',yaml:'yaml',yml:'yaml',md:'markdown',
    vue:'html',dart:'dart',lua:'lua',r:'r',m:'objectivec',
    tf:'hcl',toml:'ini',ini:'ini',txt:'plaintext'})[ext]||'plaintext';
}
function highlightCode(code, filePath){
  if(!code||code.trim()==='')return'<span style="color:#909399;font-style:italic">(empty)</span>';
  if(typeof hljs==='undefined')return'<span>'+_esc(code)+'</span>';
  const lang=_ext2lang(filePath||'');
  try{
    return hljs.highlight(code,{language:lang,ignoreIllegals:true}).value;
  }catch(_){
    return hljs.highlightAuto(code).value;
  }
}

createApp({
  setup(){
    const dialogVisible=ref(false);
    const currentIdx=ref(-1);
    const activeTab=ref('ai');
    const isAnalyzing=ref(false);
    const progressLog=ref('');
    const thinkingLog=ref('');
    const thinkingVisible=ref(false);
    const aiResultHtml=ref('<em style="color:#909399">点击「重新分析」获取 AI 分析…</em>');
    const changeStatuses=reactive({});
    const betterVisible=ref(false);
    const betterInput=ref('');
    const analysisCache=reactive({});
    const activeJobs=reactive({});

    const currentChange=computed(()=>
      currentIdx.value>=0?(_reportData.changes||[])[currentIdx.value]:null
    );

    function openAnalysis(idx){
      const c=(_reportData.changes||[])[idx];
      if(!c)return;
      currentIdx.value=idx;
      // Default to diff tab so user sees code immediately; fall back to ai if no diff data
      activeTab.value=(c.after||c.before||c.diff_html)?'diff':'ai';
      dialogVisible.value=true;
      const cached=analysisCache[idx];
      if(cached){
        progressLog.value=cached.progress||'';
        thinkingLog.value=cached.thinking||'';
        thinkingVisible.value=!!(cached.thinking);
        aiResultHtml.value=cached.resultHtml||'';
      }else{
        progressLog.value='';thinkingLog.value='';thinkingVisible.value=false;
        aiResultHtml.value='<em style="color:#909399">⏳ 正在分析…</em>';
        runAnalysis();
      }
    }
    window.openAnalysis=openAnalysis;

    function closeDialog(){ dialogVisible.value=false; }

    async function runAnalysis(extraPrompt=''){
      const idx=currentIdx.value;
      if(idx<0)return;
      if(activeJobs[idx]){ElMessage.warning('分析进行中，请稍候…');return;}
      const change=(_reportData.changes||[])[idx];
      if(!change)return;
      isAnalyzing.value=true;activeJobs[idx]=true;
      progressLog.value='🔄 准备 AI 分析...\n';
      thinkingLog.value='';thinkingVisible.value=false;
      aiResultHtml.value='<em style="color:#909399">⏳ 正在分析…</em>';
      const logMsg=msg=>{progressLog.value+=msg+'\n';};
      const prompt=(extraPrompt?extraPrompt+'\n\n':'')+
        'Analyze this code change in '+change.file_path+'. '+
        'Reply in Chinese unless instructed otherwise. Format in markdown.\n\n'+
        'Before:\n```\n'+(change.before||'(empty)')+'\n```\n\n'+
        'After:\n```\n'+(change.after||'(empty)')+'\n```\n\n'+
        'Cover: 1) purpose 2) code quality 3) potential issues 4) overall assessment.';
      const cfg=_aiConfig||{};
      try{
        logMsg('📡 连接 AI ['+( cfg.provider||'?')+' / '+(cfg.model||'?')+']...');
        const r=await fetch(api('/api/ai/chat'),{
          method:'POST',headers:{'content-type':'application/json'},
          body:JSON.stringify({
            provider:cfg.provider||'openai',api_key:cfg.api_key||cfg.apiKey||'',
            base_url:cfg.base_url||cfg.baseUrl||'',model:cfg.model||'',
            messages:[{role:'user',content:prompt}]
          })
        });
        if(!r.ok)throw new Error('Server error '+r.status);
        const {job_id}=await r.json();
        for(let i=0;i<600;i++){
          await new Promise(r=>setTimeout(r,500));
          const jr=await fetch(api('/api/ai/job/'+job_id));
          if(!jr.ok)continue;
          const job=await jr.json();
          if(job.partial){aiResultHtml.value=renderMd(job.partial);}
          const el=job.elapsed?` (${job.elapsed}s)`:'';
          const lines=progressLog.value.split('\n').filter(Boolean);
          const li=lines.length-1;
          if(li>=0&&lines[li].startsWith('⏳'))lines[li]='⏳ 生成中'+el+'...';
          else lines.push('⏳ 生成中'+el+'...');
          progressLog.value=lines.join('\n')+'\n';
          if(job.thinking){thinkingLog.value=job.thinking;thinkingVisible.value=true;}
          if(job.done&&job.ok){
            aiResultHtml.value=renderMd(job.text||job.partial||'');
            await nextTick();
            document.querySelectorAll('.ai-result-box pre code').forEach(el=>{
              if(typeof hljs!=='undefined')hljs.highlightElement(el);
            });
            logMsg('✅ 分析完成！');
            analysisCache[idx]={progress:progressLog.value,thinking:thinkingLog.value,resultHtml:aiResultHtml.value};
            break;
          }
          if(job.done&&!job.ok)throw new Error(job.error||'AI job failed');
        }
      }catch(err){
        logMsg('❌ 错误: '+(err.message||String(err)));
        aiResultHtml.value='<p style="color:#f56c6c">⚠ '+(err.message||String(err))+'</p>';
      }finally{
        delete activeJobs[idx];isAnalyzing.value=false;
      }
    }

    async function applyChange(idx,stateName){
      changeStatuses[idx]=stateName;
      const card=document.getElementById('card-'+idx);
      if(card){card.classList.remove('accepted','rejected');card.classList.add(stateName);}
      const badge=document.getElementById('badge-'+idx);
      if(badge){
        badge.className='status-badge '+stateName;
        badge.textContent=stateName==='accepted'?'✓ 已接受':'⚠ 风险';
      }
      localStorage.setItem('th-rc-'+idx,stateName);
      if(!_sidecarId)return;
      const action=stateName==='accepted'?'accept':'reject';
      try{
        const resp=await fetch(api('/api/report/apply-change'),{
          method:'POST',headers:{'content-type':'application/json'},
          body:JSON.stringify({sidecar_id:_sidecarId,change_index:idx,action})
        });
        const data=await resp.json();
        if(data.ok)ElMessage.success(stateName==='accepted'?'✓ 变更已写入文件':'文件已还原');
        else ElMessage.error('操作失败: '+(data.detail||data.error||'unknown'));
      }catch(e){ElMessage.error('操作失败: '+String(e));}
    }

    function markAccepted(){applyChange(currentIdx.value,'accepted');}
    function markRejected(){applyChange(currentIdx.value,'rejected');}
    function requestBetter(){betterInput.value='';betterVisible.value=true;}
    function confirmBetter(){
      const req=betterInput.value.trim();betterVisible.value=false;
      if(!req)return;
      activeTab.value='ai';progressLog.value='';thinkingLog.value='';
      aiResultHtml.value='<em style="color:#909399">⏳ 正在分析…</em>';
      delete analysisCache[currentIdx.value];
      runAnalysis(req);
    }

    // Restore marks from localStorage
    ;((_reportData.changes||[])).forEach((_,idx)=>{
      const s=localStorage.getItem('th-rc-'+idx);
      if(!s)return;
      changeStatuses[idx]=s;
      const card=document.getElementById('card-'+idx);
      if(card)card.classList.add(s);
      const badge=document.getElementById('badge-'+idx);
      if(badge){badge.className='status-badge '+s;badge.textContent=s==='accepted'?'✓ 已接受':'⚠ 风险';}
    });

    return{
      dialogVisible,currentIdx,activeTab,isAnalyzing,
      progressLog,thinkingLog,thinkingVisible,aiResultHtml,
      changeStatuses,betterVisible,betterInput,
      currentChange,closeDialog,runAnalysis,markAccepted,markRejected,
      requestBetter,confirmBetter,highlightCode
    };
  },
  template:`
    <el-dialog v-model="dialogVisible"
      :title="currentChange ? currentChange.file_path : 'AI 分析'"
      width="78%" top="4vh" draggable class="th-ai-dialog"
      destroy-on-close>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="📊 代码对比" name="diff">
          <div v-if="currentChange">
            <div class="diff-grid">
              <div>
                <div class="diff-pane-label">变更前</div>
                <div v-if="!currentChange.before" class="code-pre" style="display:flex;align-items:center;justify-content:center;color:#909399;font-size:12px;min-height:80px;gap:6px">
                  <span style="font-size:18px">📄</span>
                  <span>{{ currentChange.change_type==='created'?'新建文件，无历史版本':'(empty)' }}</span>
                </div>
                <pre v-else class="code-pre hljs" v-html="highlightCode(currentChange.before, currentChange.file_path)"></pre>
              </div>
              <div>
                <div class="diff-pane-label">变更后</div>
                <pre class="code-pre hljs" v-html="highlightCode(currentChange.after, currentChange.file_path)"></pre>
              </div>
            </div>
            <div v-if="currentChange.diff_html" class="diff-rendered" v-html="currentChange.diff_html"></div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="🤖 AI 分析" name="ai">
          <div v-if="progressLog" class="ai-progress-text">{{ progressLog }}</div>
          <div v-if="thinkingVisible" class="ai-thinking-box">
            <div class="ai-thinking-label">💭 思考过程</div>
            <div class="ai-thinking-text">{{ thinkingLog }}</div>
          </div>
          <div class="ai-result-box" v-html="aiResultHtml"></div>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <div class="dialog-footer">
          <el-tag v-if="changeStatuses[currentIdx]==='accepted'" type="success" size="small">✓ 已接受</el-tag>
          <el-tag v-else-if="changeStatuses[currentIdx]==='rejected'" type="danger" size="small">⚠ 风险</el-tag>
          <span style="flex:1"></span>
          <el-button size="small" @click="closeDialog">关闭</el-button>
          <el-button size="small" type="warning" plain @click="requestBetter">💡 优化方案</el-button>
          <el-button size="small" type="danger" plain @click="markRejected">⚠ 标记风险</el-button>
          <el-button size="small" type="success" plain @click="markAccepted">✓ 接受变更</el-button>
          <el-button size="small" type="primary" :loading="isAnalyzing" @click="runAnalysis()">🔄 重新分析</el-button>
        </div>
      </template>
    </el-dialog>
    <el-dialog v-model="betterVisible" title="💡 请求优化方案" width="480px" append-to-body>
      <el-input v-model="betterInput" type="textarea" :rows="4"
        placeholder="描述优化需求，例如：优化性能、增加错误处理、添加类型注解…" />
      <template #footer>
        <el-button @click="betterVisible=false">取消</el-button>
        <el-button type="primary" @click="confirmBetter">提交请求</el-button>
      </template>
    </el-dialog>
  `
}).use(ElementPlus).mount('#vueApp');

// ── AI config toolbar ─────────────────────────────────────────────────────────
(function(){
  const SK='th-report-ai-cfg';
  function cfg(){
    const s=JSON.parse(localStorage.getItem(SK)||'null')||_aiConfig||{};
    return{
      provider:document.getElementById('rProvider').value,
      model:   document.getElementById('rModel').value,
      base_url:document.getElementById('rBaseUrl').value,
      api_key: document.getElementById('rApiKey').value,
      ...s,
      provider:document.getElementById('rProvider').value,
      model:   document.getElementById('rModel').value,
    };
  }
  function saveCfg(){localStorage.setItem(SK,JSON.stringify(cfg()));}
  function bootstrap(){
    const s=JSON.parse(localStorage.getItem(SK)||'null')||_aiConfig||{};
    document.getElementById('rProvider').value=s.provider||'openai';
    document.getElementById('rModel').value   =s.model||'';
    document.getElementById('rBaseUrl').value =s.base_url||s.baseUrl||'';
    document.getElementById('rApiKey').value  =s.api_key||s.apiKey||'';
    ['rProvider','rModel','rBaseUrl','rApiKey'].forEach(id=>
      document.getElementById(id).addEventListener('change',()=>{
        const c=cfg();c.provider=document.getElementById('rProvider').value;
        c.model=document.getElementById('rModel').value;
        c.base_url=document.getElementById('rBaseUrl').value;
        c.api_key=document.getElementById('rApiKey').value;
        localStorage.setItem(SK,JSON.stringify(c));
        // Sync to global _aiConfig used by Vue app
        Object.assign(_aiConfig,c);
      })
    );
  }
  window._testConn=async function(){
    const dot=document.getElementById('statusDot');dot.classList.remove('ok');
    const btn=event.currentTarget;if(btn)btn.disabled=true;
    try{
      const c=cfg();
      const r=await fetch(window.location.origin+'/api/ai/test',{
        method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(c)
      });
      const d=await r.json();
      if(d.ok){dot.classList.add('ok');ElMessage.success('✅ '+(d.message||'Connected').slice(0,100));}
      else ElMessage.error('❌ '+(d.message||'Failed').slice(0,100));
    }catch(e){ElMessage.error('连接失败: '+e.message);}
    finally{if(btn)btn.disabled=false;}
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bootstrap);
  else bootstrap();
})();
</script>
"""


class ReportGenerator:
    def strip_ansi(self, text: str) -> str:
        return ANSI_RE.sub("", text)

    def generate_report(
        self,
        terminal: dict[str, Any],
        log_text: str,
        code_changes: list[dict[str, Any]],
        lang: str = "zh",
        ai_summary: str = "",
        ai_provider_config: dict[str, Any] | None = None,
        git_info: dict[str, Any] | None = None,
        sidecar_id: str = "",
    ) -> str:
        clean_log = self.strip_ansi(log_text)
        created_at = datetime.fromtimestamp(terminal.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
        lines_added = lines_removed = 0
        for ch in code_changes:
            for line in ch.get("diff", "").splitlines():
                if line.startswith(("+++", "---")):
                    continue
                if line.startswith("+"):
                    lines_added += 1
                elif line.startswith("-"):
                    lines_removed += 1

        locale = {
            "zh": {
                "title": "TerminalHub 会话报告",
                "summary": "会话摘要", "log": "终端日志", "changes": "代码变更",
                "analysis": "AI 分析摘要", "duration": "会话时长",
                "files": "变更文件数", "lines": "代码行变化",
                "generated": "生成时间", "provider": "AI 提供商", "test": "测试连接",
                "before": "变更前", "after": "变更后",
            },
            "en": {
                "title": "TerminalHub Session Report",
                "summary": "Session Summary", "log": "Terminal Log", "changes": "Code Changes",
                "analysis": "AI Analysis Summary", "duration": "Duration",
                "files": "Changed Files", "lines": "Line Changes",
                "generated": "Generated At", "provider": "AI Provider", "test": "Test",
                "before": "Before", "after": "After",
            },
        }.get(lang, {})
        if not locale:
            locale = {"title": "TerminalHub Session Report", "summary": "Summary",
                      "log": "Log", "changes": "Changes", "analysis": "AI Analysis",
                      "duration": "Duration", "files": "Files", "lines": "Lines",
                      "generated": "Generated", "provider": "Provider", "test": "Test",
                      "before": "Before", "after": "After"}

        duration_sec = max(0, int(datetime.now().timestamp() - float(terminal.get("created_at", 0))))
        duration_text = f"{duration_sec // 3600}h {(duration_sec % 3600) // 60}m {duration_sec % 60}s"

        def _safe_json(obj: Any) -> str:
            return json.dumps(obj, ensure_ascii=False).replace("</", r"<\/")

        _MAX = 4000
        def slim(changes: list) -> list:
            result = []
            for c in changes:
                s = {k: v for k, v in c.items() if k not in ("before", "after", "diff")}
                s["before"] = (c.get("before") or "")[:_MAX]
                s["after"]  = (c.get("after")  or "")[:_MAX]
                s["diff_html"] = (c.get("diff_html") or "")[:8000]
                result.append(s)
            return result

        changes_js  = _safe_json(slim(code_changes))
        ai_config_js = _safe_json(ai_provider_config or {})
        sidecar_js  = _safe_json(sidecar_id)
        git_js      = _safe_json(git_info or {})

        # ── Git bar ──────────────────────────────────────────────────────────
        gi = git_info or {}
        git_bar = ""
        if gi.get("is_git"):
            git_bar = (
                f'<div class="git-bar">'
                f'<span class="git-chip"><span>⎇</span>{escape(gi.get("branch",""))}</span>'
                f'<span class="git-chip mono" title="HEAD">{escape(gi.get("commit",""))}</span>'
                f'<span class="git-chip mono muted" title="prev">← {escape(gi.get("prev_commit",""))}</span>'
                f'<span class="git-msg" title="{escape(gi.get("message",""))}">{escape((gi.get("message") or "")[:72])}</span>'
                f'<span class="git-meta">{escape(gi.get("author",""))} · {escape(gi.get("date",""))}</span>'
                f'</div>'
            )

        # ── Change cards ─────────────────────────────────────────────────────
        card_html_parts = []
        for idx, ch in enumerate(code_changes):
            fp     = escape(ch.get("file_path", ""))
            ct     = escape(ch.get("change_type", "modified"))
            lg     = escape(ch.get("language", "text"))
            icon   = _LANG_ICONS.get((ch.get("language") or "text").lower(), "📄")
            card_html_parts.append(
                f'<div class="change-card" id="card-{idx}" onclick="openAnalysis({idx})">'
                f'  <span class="lang-icon">{icon}</span>'
                f'  <div class="change-card-info">'
                f'    <div class="file-path">{fp}</div>'
                f'    <div class="card-tags">'
                f'      <span class="tag-chip {ct}">{ct}</span>'
                f'      <span class="tag-chip">{lg}</span>'
                f'    </div>'
                f'  </div>'
                f'  <div class="change-card-right">'
                f'    <span class="status-badge" id="badge-{idx}"></span>'
                f'    <button class="btn-analyze" onclick="event.stopPropagation();openAnalysis({idx})">🤖 AI 分析</button>'
                f'  </div>'
                f'</div>'
            )
        cards_html = "\n".join(card_html_parts) if card_html_parts else '<p style="color:#909399">暂无代码变更</p>'

        ai_sum_html = (
            f'<div class="card">'
            f'  <div class="card-title">✨ {escape(locale["analysis"])}</div>'
            f'  <div class="ai-summary-text">{escape(ai_summary)}</div>'
            f'</div>'
        ) if ai_summary else ""

        n = len(code_changes)
        title_esc = escape(terminal.get("title", "Terminal"))
        pid_esc   = escape(str(terminal.get("pid", "")))
        shell_esc = escape(terminal.get("shell", ""))
        cwd_esc   = escape(terminal.get("cwd", ""))
        desc_esc  = escape(terminal.get("description", ""))
        loc_title = escape(locale["title"])
        loc_sum   = escape(locale["summary"])
        loc_log   = escape(locale["log"])
        loc_chg   = escape(locale["changes"])
        loc_dur   = escape(locale["duration"])
        loc_files = escape(locale["files"])
        loc_lines = escape(locale["lines"])
        loc_gen   = escape(locale["generated"])
        loc_test  = escape(locale["test"])
        loc_prov  = escape(locale["provider"])

        html_parts: list[str] = []
        html_parts.append(f'<!DOCTYPE html><html lang="{escape(lang)}">')
        html_parts.append(f"""<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{loc_title} · {title_esc}</title>
<link rel="stylesheet" href="https://unpkg.com/element-plus/dist/index.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
<style>{_CSS}</style>
</head>""")

        html_parts.append(f"""<body>
<div class="page">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-brand">
      <div class="toolbar-brand-icon">⬡</div>
      <div>
        <div class="toolbar-title">{loc_title} · {title_esc}</div>
        <div class="toolbar-sub">PID {pid_esc} · {shell_esc} · {cwd_esc}</div>
      </div>
    </div>
    <div class="toolbar-right">
      <div class="ai-cfg-row">
        <span>{loc_prov}</span>
        <select id="rProvider">
          <option value="copilot">Copilot</option>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="deepseek">DeepSeek</option>
          <option value="qwen">Qwen</option>
          <option value="ollama">Ollama</option>
          <option value="custom">Custom</option>
        </select>
        <input id="rModel" placeholder="model" style="width:110px">
        <input id="rBaseUrl" placeholder="base url" style="width:120px">
        <input id="rApiKey" type="password" placeholder="api key" style="width:90px">
        <span id="statusDot" class="status-dot"></span>
        <button class="btn btn-default" onclick="_testConn()">{loc_test}</button>
      </div>
    </div>
  </div>

  <!-- Git bar -->
  {git_bar}

  <!-- Stats -->
  <div class="stats-row">
    <div class="stat-card"><div class="stat-label">{loc_dur}</div><div class="stat-value">{escape(duration_text)}</div></div>
    <div class="stat-card"><div class="stat-label">{loc_files}</div><div class="stat-value">{n}</div></div>
    <div class="stat-card"><div class="stat-label">+ {loc_lines}</div><div class="stat-value green">+{lines_added}</div></div>
    <div class="stat-card"><div class="stat-label">- {loc_lines}</div><div class="stat-value red">-{lines_removed}</div></div>
    <div class="stat-card"><div class="stat-label">{loc_gen}</div><div class="stat-value" style="font-size:13px;margin-top:4px">{escape(created_at)}</div></div>
  </div>

  {ai_sum_html}

  <!-- Terminal log -->
  <div class="card">
    <div class="card-title">🖥 {loc_log}</div>
    <div class="terminal-log">{escape(clean_log)}</div>
  </div>

  <!-- Change cards -->
  <div class="card">
    <div class="card-title">📁 {loc_chg} · {n} 个文件</div>
    {cards_html}
  </div>

  <div class="footer">Generated by TerminalHub · {escape(created_at)}</div>
</div>

<!-- Vue app mount -->
<div id="vueApp"></div>

<!-- Data -->
<script>
const _reportData = {{ changes: {changes_js} }};
const _aiConfig   = {ai_config_js};
const _sidecarId  = {sidecar_js};
const _gitInfo    = {git_js};
</script>

<!-- CDN -->
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<script src="https://unpkg.com/element-plus/dist/index.full.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
""")

        html_parts.append(_VUE_SCRIPT)
        html_parts.append("</body></html>")

        return "\n".join(html_parts)
