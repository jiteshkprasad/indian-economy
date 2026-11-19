import json,glob,sys,statistics
d=sys.argv[1]
rows=[]
for f in sorted(glob.glob(d+'/lhr-*.json')):
    j=json.load(open(f))
    a=j['audits'];c=j['categories']
    rows.append(dict(url=j['finalDisplayedUrl'] if 'finalDisplayedUrl' in j else j['finalUrl'],ff=j['configSettings']['formFactor'],thr=j['configSettings']['throttlingMethod'],
      perf=c['performance']['score'],a11y=c['accessibility']['score'],bp=c.get('best-practices',{}).get('score'),seo=c.get('seo',{}).get('score'),
      lcp=a['largest-contentful-paint']['numericValue'],fcp=a['first-contentful-paint']['numericValue'],tbt=a['total-blocking-time']['numericValue'],cls=a['cumulative-layout-shift']['numericValue'],si=a['speed-index']['numericValue'],
      lv=j['lighthouseVersion'],ua=j['environment'].get('hostUserAgent','')[:60]))
for r in rows: print(r)
for k in ['perf','a11y','bp','lcp','tbt','fcp','cls','si']:
    print(k,'median',statistics.median([r[k] for r in rows]))
# failing audits from first
j=json.load(open(sorted(glob.glob(d+'/lhr-*.json'))[0]))
for cat in ['accessibility','best-practices','seo','performance']:
    for ref in j['categories'][cat]['auditRefs']:
        au=j['audits'][ref['id']]
        if au.get('score') is not None and au['score']<0.9 and au['scoreDisplayMode'] not in('informative','notApplicable','manual'):
            print(cat,ref['id'],au['score'],au.get('displayValue',''),au['title'])
