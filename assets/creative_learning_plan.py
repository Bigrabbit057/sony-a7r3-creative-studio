"""Standalone source generator for the original six-slot learner."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
IDS=['kodak-ektachrome-e100','reala-ace','fuji-c200','kodak-gold-200','provia','ilford-hp5']

def body():
    library=json.loads((ROOT/'recipes.json').read_text(encoding='utf-8'))['recipes']
    byid={r['id']:r for r in library};rr=[byid[k] for k in IDS]
    initial='\n'.join(f'cs_a{i}={round(r["wb"]["ab"]*1000)}; cs_c{i}={round(-r["wb"]["gm"]*1000)}' for i,r in enumerate(rr))
    load='\n'.join(f'{i}) cs_ab=$cs_a{i}; cs_cc=$cs_c{i} ;;' for i in range(6))
    store='\n'.join(f'{i}) cs_a{i}=$2; cs_c{i}=$3 ;;' for i in range(6))
    template=(ROOT/'creative_learning_runtime.sh').read_text(encoding='utf-8')
    return template.replace('__INITIAL__',initial).replace('__LOAD__',load).replace('__STORE__',store).encode('ascii')
