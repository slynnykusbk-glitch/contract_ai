import pathlib

HTML = pathlib.Path('word_addin_dev/taskpane.html').read_text(encoding='utf-8')


def _exists(id_sel: str, role: str) -> bool:
    return (f'id="{id_sel}"' in HTML) or (f'data-role="{role}"' in HTML)


def test_clause_type_slot_exists():
    assert _exists('resClauseType', 'clause-type')


def test_findings_list_slot_exists():
    assert _exists('findingsList', 'findings')


def test_recommendations_list_slot_exists():
    assert _exists('recoList', 'recommendations')


def test_raw_json_toggle_slot_exists():
    assert _exists('toggleRaw', 'toggle-raw-json')


def test_raw_json_pre_slot_exists():
    assert _exists('rawJson', 'raw-json')


def test_accept_all_button_exists():
    assert _exists('btnAcceptAll', '')


def test_reject_all_button_exists():
    assert _exists('btnRejectAll', '')


def test_accept_reject_click_smoke():
    import subprocess, textwrap
    js = textwrap.dedent(
        """
        const fs = require('fs');
        const vm = require('vm');
        const code = fs.readFileSync('word_addin_dev/taskpane.bundle.js', 'utf8');

        function el(){
          return {
            textContent:'', value:'', style:{},
            classList:{remove(){}},
            addEventListener(ev,fn){this.fn=fn;},
            removeAttribute(){}, dispatchEvent(){},
            click(){this.fn&&this.fn({preventDefault(){}})}
          }
        }

        const btnA=el(), btnR=el(), prop={value:'hi',dispatchEvent(){}};
        const cidEl={textContent:'cid123'};
        const doc={
          readyState:'complete',
          querySelector(s){ if(s==='#btnAcceptAll') return btnA; if(s==='#btnRejectAll') return btnR; if(s.includes('#proposedText')) return prop; return null; },
          getElementById(id){ if(id==='btnAcceptAll') return btnA; if(id==='btnRejectAll') return btnR; if(id==='cid') return cidEl; return el(); },
          body: el()
        };
        const win={document:doc, toast(){}};
        global.fetch=async()=>({ok:true,headers:{get(){return null;}},json:async()=>({status:'ok',schema:'1'}),status:200});
        global.Event=function(){};
        const ctx={
          window:win,
          document:doc,
          self:win,
          console:console,
          Word:{
            run:async fn=>{
              const range={insertText(){},insertComment(){},revisions:{load(){},items:[{reject(){}}]}};
              await fn({document:{getSelection(){return range;}},sync:async()=>{}});
            }
          },
          Office:{},
          navigator:{clipboard:{writeText:async()=>{}}},
          localStorage:{getItem(){return null;}},
          Event:function(){}
        };
        vm.createContext(ctx); vm.runInContext(code, ctx);
        btnA.click(); btnR.click();
        """
    )
    subprocess.run(['node', '-e', js], check=True)
