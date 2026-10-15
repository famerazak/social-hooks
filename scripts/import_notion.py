#!/usr/bin/env python3
"""Import the public content-prompt database using Notion's public web endpoints."""
import concurrent.futures, csv, datetime, hashlib, json, pathlib, sqlite3, subprocess
BASE='https://workable-fedora-9e0.notion.site'
ROOT='31372a07-7ac7-8186-b6fc-fb89ffa02db8'
VIEW='31372a07-7ac7-8103-98bb-000ca2522c4b'
COL='31372a07-7ac7-81a2-a762-000b87e52b41'
OUT=pathlib.Path(__file__).resolve().parents[1]/'data/notion'
RAW=OUT/'raw'
def unwrap(v):
    while isinstance(v,dict) and 'value' in v: v=v['value']
    return v

def api(endpoint,payload,name):
    r=subprocess.run(['curl','--fail-with-body','-sS','--max-time','45',BASE+'/api/v3/'+endpoint,'-H','Content-Type: application/json','--data-binary','@-'],input=json.dumps(payload),text=True,capture_output=True)
    if r.returncode: raise RuntimeError(f'{endpoint}: curl exit {r.returncode}: {r.stderr[:200]}')
    data=json.loads(r.stdout)
    if data.get('isNotionError'): raise RuntimeError(str(data))
    (RAW/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return data

def load(page):
    result={}; cursor={'stack':[]}; number=0
    while True:
        x=api('loadPageChunk',{'pageId':page,'limit':100,'cursor':cursor,'chunkNumber':number,'verticalColumns':False},page+'-'+str(number))
        for k,v in x.get('recordMap',{}).get('block',{}).items(): result[k]=unwrap(v)
        cursor=x.get('cursor',{'stack':[]})
        if not cursor.get('stack'): return result
        number+=1
        if number>100: raise RuntimeError('Unexpected pagination depth')

def text(v):
    if isinstance(v,str): return v
    if not isinstance(v,list): return ''
    parts=[]
    for segment in v:
        if not isinstance(segment,list) or not segment: continue
        s=segment[0]
        for a in segment[1] if len(segment)>1 else []:
            if a[0]=='d' and isinstance(a[1],dict): s=a[1].get('start_date','')+(' / '+a[1]['end_date'] if a[1].get('end_date') else '')
        parts.append(s)
    return ''.join(parts)

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    root=api('loadPageChunk',{'pageId':ROOT,'limit':100,'cursor':{'stack':[]},'chunkNumber':0,'verticalColumns':False},'root')
    query=api('queryCollection',{'collectionId':COL,'collectionViewId':VIEW,'query':{},'loader':{'type':'reducer','reducers':{'collection_group_results':{'type':'results','limit':10000}},'searchQuery':'','userTimeZone':'Europe/Madrid'}},'collection')
    result=query['result']['reducerResults']['collection_group_results']
    if result.get('hasMore'): raise RuntimeError('Collection truncated; pagination required')
    current=result['blockIds']; blocks={k:unwrap(v) for k,v in query['recordMap']['block'].items()}
    view=unwrap(root['recordMap']['collection_view'][VIEW]); saved=view.get('page_sort',[])
    targets=set(saved)-set(blocks)
    targets.update(k for k,v in blocks.items() if v.get('content'))
    errors={}
    def fetch(i):
        try: return i,load(i),None
        except Exception as e: return i,{},str(e)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for i,bs,error in pool.map(fetch,sorted(targets)):
            if error: errors[i]=error
            blocks.update(bs)
    # Fetch any content descendants not returned by the initial chunks.
    seen=set(targets)
    while True:
        missing={i for b in blocks.values() for i in b.get('content',[]) if i not in blocks}-seen
        if not missing: break
        for i in sorted(missing):
            seen.add(i); _,bs,error=fetch(i);blocks.update(bs)
            if error: errors[i]=error
    collection=unwrap(query['recordMap']['collection'][COL]);schema=collection['schema']
    rows=[]
    def body(i,visited=None):
        visited=set() if visited is None else visited
        if i in visited:return ''
        visited.add(i);b=blocks.get(i,{})
        return '\n'.join(filter(None,[text(b.get('properties',{}).get('title',[])),*[body(c,visited) for c in b.get('content',[])]]))
    ids=list(dict.fromkeys(current+[i for i in saved if blocks.get(i,{}).get('alive') and blocks.get(i,{}).get('parent_id')==COL]))
    for i in ids:
        b=blocks[i];props=b.get('properties',{})
        row={'id':i,'source_url':BASE+'/'+i.replace('-',''),'in_current_query':i in current}
        row.update({v['name'].strip():text(props.get(k,[])) for k,v in schema.items()})
        row['body']='\n'.join(body(c) for c in b.get('content',[]))
        row['created_time']=b.get('created_time');row['last_edited_time']=b.get('last_edited_time')
        row['properties_raw']=props; rows.append(row)
    (OUT/'prompts.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    columns=[k for k in rows[0] if k!='properties_raw']
    with (OUT/'prompts.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    db=sqlite3.connect(OUT/'prompts.sqlite3')
    db.execute('DROP TABLE IF EXISTS prompts');db.execute('DROP TABLE IF EXISTS prompts_fts')
    db.execute('CREATE TABLE prompts (id TEXT PRIMARY KEY, prompt TEXT, pillar TEXT, format TEXT, best_for TEXT, week TEXT, instagram_url TEXT, notes TEXT, niche_examples TEXT, body TEXT, source_url TEXT, raw_json TEXT)')
    db.execute('CREATE VIRTUAL TABLE prompts_fts USING fts5(id UNINDEXED,prompt,notes,niche_examples,body)')
    for r in rows:
        vals=[r['id'],r['Content Prompt'],r['Content Pillar'],r['Type of Content'],r['Best For'],r['Week'],r['Example on IG'],r['Notes'],r['Niche Adaptation Examples'],r['body'],r['source_url'],json.dumps(r,ensure_ascii=False)]
        db.execute('INSERT INTO prompts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        db.execute('INSERT INTO prompts_fts VALUES (?,?,?,?,?)',[r['id'],r['Content Prompt'],r['Notes'],r['Niche Adaptation Examples'],r['body']])
    db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
    missing_content=sorted({i for b in blocks.values() for i in b.get('content',[]) if i not in blocks})
    manifest={'title':text(collection['name']),'description':text(collection.get('description',[])),'source_url':BASE+'/'+ROOT.replace('-','')+'?v='+VIEW.replace('-',''),'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current_query_count':len(current),'saved_view_reference_count':len(saved),'exported_count':len(rows),'entries_with_body':sum(bool(r['body']) for r in rows),'missing_content_blocks':missing_content,'request_errors':errors,'historical_references_not_exported':[i for i in saved if i not in ids],'scope':'Public database properties and accessible descendant blocks. External Instagram content and binary attachments are not downloaded. Raw endpoint responses preserve rich text and metadata.','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['files','historical_references_not_exported']},ensure_ascii=False,indent=2))
    if errors or missing_content:raise SystemExit('Import incomplete: see manifest')
if __name__=='__main__':main()
