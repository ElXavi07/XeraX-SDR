"""Summarize manually observed paired trials. Empty input reports pending, never a win."""
import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('csv',type=Path)
p.add_argument('--template',action='store_true')
p.add_argument('--output',type=Path)
a=p.parse_args()
fields=['trial','frequency_mhz','protocol','xerax_heard','sds100_heard','xerax_first_word','sds100_first_word','notes']
if a.template:
    with a.csv.open('x',newline='',encoding='utf-8') as f: csv.DictWriter(f,fieldnames=fields).writeheader()
    print('Empty observation template created; no measurements recorded.')
else:
    with a.csv.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=fields: raise ValueError('Use the template columns in their original order.')
        rows=list(reader)
    ids=set(); counts=dict(bothHeard=0,xeraxOnly=0,sds100Only=0,neitherHeard=0)
    for row in rows:
        if not row['trial'].strip() or row['trial'] in ids: raise ValueError('Every trial must have a unique ID.')
        ids.add(row['trial'])
        if not 24<=float(row['frequency_mhz'])<=1766: raise ValueError('Invalid frequency')
        if any(row[key] not in ('0','1') for key in fields[3:7]): raise ValueError('Scores must be 0 or 1; omit unobserved trials.')
        x,s=int(row['xerax_heard']),int(row['sds100_heard'])
        if int(row['xerax_first_word'])>x or int(row['sds100_first_word'])>s: raise ValueError('First word requires heard audio.')
        counts['bothHeard' if x and s else 'xeraxOnly' if x else 'sds100Only' if s else 'neitherHeard']+=1
    report=dict(schema=1,evidence='manual observations, not independently verified',
        status='observed' if rows else 'pending',pairedTrials=len(rows),outcomes=counts,
        firstWord=dict(xerax=sum(int(r['xerax_first_word']) for r in rows),sds100=sum(int(r['sds100_first_word']) for r in rows)),
        superiorityEstablished=False)
    text=json.dumps(report,indent=2)+'\n'
    if a.output: a.output.write_text(text,encoding='utf-8')
    print(text,end='')
