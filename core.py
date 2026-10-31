"""GPL-3.0-only. Recipe data, validation and plans; never imports USB code."""
from pathlib import Path
import copy, hashlib, json, math, re

APP=Path(__file__).resolve().parent
ASSETS=APP/'assets'
SCOPE={'model':'ILCE-7RM3','firmware':'3.10','region':'CX62001_CN2'}
P='/setting/csboot-v1';R='/tmp_bt/csboot-v1';BRIDGE='/setting/cs'
SCRIPT='/usr/bin/startBTCore.sh'
TOKEN=b'CSBOOT_CREATIVE_V1_20261027\n'
SCRIPT_SHA='33c82447cdbcdbd27e476ddf15f39f19a96d826d775e241d14ee0691d97beb27'
STYLES={'Standard':(1,'标准'),'Vivid':(2,'生动'),'Neutral':(3,'中性'),'Portrait':(4,'肖像'),
        'Landscape':(5,'风景'),'Black & White':(6,'黑白'),'Clear':(7,'清澈'),'Deep':(8,'深色'),
        'Light':(9,'浅色'),'Sunset':(10,'黄昏'),'Night':(11,'夜景'),'Autumn':(12,'红叶'),'Sepia':(14,'棕褐色')}
BASES={'style':0x0107075c,'contrast':0x01070a0f,'saturation':0x01070a15,'sharpness':0x01070a1b}
WB_CURRENT=['0x01070017','0x01070016','0x010714b6','0x010714b5']
WB_MEMORY=['0x0107067f','0x0107067e','0x010714dd','0x010714dc']
DEFAULT_IDS=['kodak-ektachrome-e100','reala-ace','fuji-c200','kodak-gold-200','provia','ilford-hp5']

def digest(value):
    if not isinstance(value,bytes):value=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(value).hexdigest()

def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def integer(value,lo,hi,label):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value!=int(value) or not lo<=value<=hi:
        raise ValueError(f'{label} 必须是 {lo}～{hi} 的整数')
    return int(value)

def step(value,unit,label):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not -7<=value<=7 or abs(value/unit-round(value/unit))>1e-8:
        raise ValueError(f'{label} 范围 −7～+7，步长 {unit}')
    return float(value)

def short_name(name):
    known={'Kodak Ektachrome E100':'E100','Reala Ace':'REALA','Fuji C200':'C200','Kodak Gold 200':'Gold 200','Provia':'PROVIA','Ilford HP5':'HP5'}
    if name in known:return known[name]
    text=re.sub(r'^(Kodak|Fuji|Ilford|Sony|Canon|Nikon)\s+','',name,flags=re.I)
    text=re.sub('[^A-Za-z0-9 +_-]','',text).strip()
    if len(text)>8:text=text.replace(' ','')
    return text[:8] or 'CUSTOM'

def validate_recipe(raw):
    allowed={'id','name','short','group','style','contrast','saturation','sharpness','wb','effect','effect_sub','ev_thirds','dro','source','notes'}
    if not isinstance(raw,dict) or set(raw)-allowed:raise ValueError('配方结构不支持')
    r=copy.deepcopy(raw)
    for key,limit in [('id',80),('name',100),('group',60),('source',500),('notes',2000)]:
        v=r.get(key,'')
        if not isinstance(v,str) or len(v)>limit:raise ValueError(f'{key} 文本无效')
        r[key]=v.strip()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',r['id']) or not r['name']:raise ValueError('配方需要有效编号和完整名称')
    if r['source'] and not re.match(r'^https://[^\s<>"\x00-\x1f]+$',r['source']):raise ValueError('来源链接必须为 HTTPS 地址')
    if not isinstance(r.get('short'),str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9 +_-]{0,7}',r['short']) or r['short']!=r['short'].strip():
        raise ValueError('相机简称为 1～8 个英文、数字、空格或 +_-，首位为英文或数字')
    if r.get('style') not in STYLES:raise ValueError('不支持的创意风格')
    for k in ('contrast','saturation','sharpness'):r[k]=integer(r.get(k),-3,3,k)
    w=r.get('wb')
    if not isinstance(w,dict) or set(w)!={'mode','kelvin','ab','gm'} or w['mode'] not in ('auto','kelvin'):raise ValueError('白平衡格式无效')
    k=integer(w['kelvin'],2500,9900,'色温')
    if k%100:raise ValueError('色温以 100K 为单位')
    r['wb']={'mode':w['mode'],'kelvin':k,'ab':step(w['ab'],.5,'A/B'),'gm':step(w['gm'],.25,'G/M')}
    r['effect']=integer(r.get('effect',0),0,13,'图片效果');r['effect_sub']=integer(r.get('effect_sub',0),0,4,'效果子参数')
    r['ev_thirds']=integer(r.get('ev_thirds',0),-15,15,'曝光补偿三分之一档')
    if r.get('dro')!='auto':r['dro']=integer(r.get('dro'),0,5,'DRO')
    return r

def compatibility(r):
    errors=[]
    if r['wb']['mode']!='auto':errors.append('当前六槽常驻程序只联动 AWB 偏移，尚不支持固定色温配方')
    if r['effect']!=0:errors.append('图片效果会覆盖创意风格，且部分效果限制 RAW；此版拒绝写入效果配方')
    return {'writable':not errors,'reasons':errors,'manual':['曝光补偿与 DRO 保存为参考值，不随槽位切换；请在相机菜单手动设置。']}

def wb_text(w):
    a=w['ab'];g=w['gm'];prefix='AWB' if w['mode']=='auto' else f"{w['kelvin']}K"
    return f"{prefix} · {('A' if a>=0 else 'B')}{abs(a):g} / {('G' if g>=0 else 'M')}{abs(g):g}"

def wb_values(w):
    if w['mode']!='auto':raise ValueError('此写入器只接受 AWB')
    a=round(w['ab']*1000);c=round(-w['gm']*1000);ai=math.trunc(a/1000);ci=math.trunc(c/1000)
    vs=[ai.to_bytes(1,'little',signed=True).hex(),ci.to_bytes(1,'little',signed=True).hex(),(a-ai*1000).to_bytes(2,'little',signed=True).hex(),(c-ci*1000).to_bytes(2,'little',signed=True).hex()]
    return {'0x01070019':'01',**dict(zip(WB_CURRENT,vs)),**dict(zip(WB_MEMORY,vs))}

def seed_bytes(recipes):
    if len(recipes)!=6:raise ValueError('必须恰好六个槽位')
    return ''.join(f"{i} {round(r['wb']['ab']*1000)} {round(-r['wb']['gm']*1000)}\n" for i,r in enumerate(recipes)).encode()

def parse_seed(raw):
    try:lines=raw.decode('ascii').splitlines();out=[]
    except Exception as e:raise ValueError('记忆编码错误') from e
    if len(lines)!=6:raise ValueError('记忆须有六行')
    for i,line in enumerate(lines):
        if not re.fullmatch(r'[0-5] -?(0|[1-9][0-9]{0,3}) -?(0|[1-9][0-9]{0,3})',line):raise ValueError('记忆格式错误')
        slot,a,c=map(int,line.split())
        if slot!=i:raise ValueError('记忆槽号错误')
        out.append({'mode':'auto','kelvin':5500,'ab':step(a/1000,.5,'A/B'),'gm':step(-c/1000,.25,'G/M')})
    return out

def record_bytes(seed,seq):
    parse_seed(seed);integer(seq,0,999999999,'记忆代数')
    body=f'CSWB1 {seq}\n'.encode()+seed
    return body+b'MD5 '+hashlib.md5(body).hexdigest().encode()+b'\n'

def parse_record(raw):
    lines=raw.splitlines()
    if len(lines)!=8 or not raw.endswith(b'\n') or not re.fullmatch(rb'CSWB1 (0|[1-9][0-9]{0,8})',lines[0]):raise ValueError('记忆记录无效')
    body=b'\n'.join(lines[:7])+b'\n'
    if lines[7]!=b'MD5 '+hashlib.md5(body).hexdigest().encode():raise ValueError('记忆校验失败')
    seed=b'\n'.join(lines[1:7])+b'\n';parse_seed(seed)
    return int(lines[0].split()[1]),seed

def choose_record(records):
    valid=[]
    for k,raw in records.items():
        try:seq,seed=parse_record(raw);valid.append((seq,k,seed))
        except ValueError:pass
    if not valid:raise ValueError('两份白平衡记忆均无效，停止操作')
    highest=max(x[0] for x in valid)
    if len({x[2] for x in valid if x[0]==highest})!=1:raise ValueError('同一代白平衡记忆互相冲突，停止操作')
    return max(valid,key=lambda row:row[0])

def library_default():
    rs=[validate_recipe(r) for r in load(ASSETS/'recipes.json')['recipes']]
    return {'format':'creative-studio-v1','recipes':rs,'assignments':DEFAULT_IDS.copy(),'active':1}

def validate_library(value):
    if not isinstance(value,dict) or value.get('format')!='creative-studio-v1' or not isinstance(value.get('recipes'),list) or not 1<=len(value['recipes'])<=500:raise ValueError('配方库格式无效，支持 1～500 项')
    rs=[validate_recipe(r) for r in value['recipes']];ids=[r['id'] for r in rs]
    if len(ids)!=len(set(ids)):raise ValueError('配方编号重复')
    slots=value.get('assignments',[])
    if not isinstance(slots,list) or len(slots)!=6 or any(x not in ids for x in slots):raise ValueError('必须为六个槽位选择有效配方')
    return {'format':'creative-studio-v1','recipes':rs,'assignments':slots.copy(),'active':integer(value.get('active',1),1,6,'启用槽位')}

def build_plan(snapshot,recipes,active):
    if snapshot['identity']!=SCOPE:raise ValueError('只接受 ILCE-7RM3 原版 / 3.10 / CX62001_CN2')
    if snapshot['installation'] not in ('legacy-v1','legacy-resource-v2','studio-v1'):raise ValueError('相机组件未安装或版本未知，请先核对组件状态')
    if len(recipes)!=6:raise ValueError('需要六套配方')
    recipes=[validate_recipe(r) for r in recipes];active=integer(active,1,6,'启用槽位')
    reasons=[f"槽{i+1} {r['name']}："+'；'.join(compatibility(r)['reasons']) for i,r in enumerate(recipes) if not compatibility(r)['writable']]
    if reasons:raise ValueError('\n'.join(reasons))
    before=snapshot['values'];target={};display=[]
    for i,r in enumerate(recipes):
        for field,base in BASES.items():
            key=f'0x{base+i:08x}';n=STYLES[r['style']][0] if field=='style' else r[field]
            target[key]=n.to_bytes(1,'little',signed=True).hex()
        display.append({'slot':i+1,'before':snapshot['slots'][i],'after':r,'reference':f"曝光 {r['ev_thirds']/3:+.1f} EV / DRO {r['dro']}（手动参考）"})
    # 0x01070187 is saturation, NOT Picture Effect. Effect-off is a separate
    # explicit menu prerequisite until its A7R III property is verified.
    target.update(wb_values(recipes[active-1]['wb']));target['0x0107031c']='00';target['0x01070762']=f'{active-1:02x}'
    for k,v in target.items():
        if k not in before or len(before[k])!=len(v):raise ValueError('相机字段或长度不匹配')
    changes={k:v for k,v in target.items() if before[k]!=v}
    return {'before':copy.deepcopy(snapshot),'recipes':recipes,'active':active,'changes':changes,'after':{**before,**changes},'display':display,
            'names':[r['short'] for r in recipes],'seed_hex':seed_bytes(recipes).hex(),'binding':digest(snapshot)}

WARNING_STEPS=[
 ('可能变砖','这是实验性持久固件文件修改，不是索尼官方升级。可能无法开机、丢失设置或数据、影响保修，严重时需要拆机维修或更换主板。确认窗口不能消除这些风险。'),
 ('严格核对机型','唯一实测参考：原版 Sony A7R III，ILCE-7RM3，原厂固件 3.10，区域 CX62001_CN2。不是 ILCE-7RM3A（A7R IIIA），也不是 A7 III。其他版本、区域、文件或内存布局不匹配会拒绝安装，不能靠勾选强行绕过。'),
 ('供电与个人备份','请先备份照片和重要设置，电池充足，使用稳定 USB 线，关闭会抢占相机的软件；关闭电脑睡眠。安装、校验和退出服务完成之前，不拔线、不关机、不取电池。'),
 ('救援能力有限','工具会保存这台相机自己的设置、组件和两遍 /usr 分区备份，并准备精确回退；但 USB 失联、断电或无法进入服务模式时，不能保证恢复。备份不是硬件救砖通道，也不能刷其他人的分区镜像。'),
 ('自愿承担实验风险','本软件按原样提供，不作适用性或可靠性保证；法律允许范围内不承担损失责任，不排除不可排除的法定责任。此次在其他同型号机身上的移植仍未实机验证。请核对下方实测身份，再输入确认短语。')]
CONFIRM_PHRASE='ILCE-7RM3 3.10 我理解可能变砖'

def schema():return {'scope':SCOPE,'styles':{k:v[1] for k,v in STYLES.items()},'warning_steps':[{'title':t,'body':b} for t,b in WARNING_STEPS],'confirm_phrase':CONFIRM_PHRASE,'name_max':8,'version':'0.1.4-experimental'}
