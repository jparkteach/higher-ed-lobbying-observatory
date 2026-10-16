"""Reconstruct Camp (2021), chapter 3, on the supplied 2015–2024 panel.
Run with Python 3.12 and pandas, numpy, scipy, statsmodels (see requirements.txt).
The source CSV is never modified. All conventions are explained in the report.
"""
from pathlib import Path
import argparse, hashlib, json, warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
SITE = ROOT / 'docs'
CPI = {2015:237.017,2016:240.007,2017:245.120,2018:251.107,2019:255.657,
       2020:258.811,2021:270.970,2022:292.655,2023:304.702,2024:313.689}
CPI_URL = 'https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm'
FLAGS = ['landgrant','hbcu','doctoral','aau','hospital','medical','hsi','tribal','msi']
TERMS = ['rd10','pell10','private','forprofit','landgrant','hbcu','doctoral','aau',
         'hospital','medical','enroll1000','budget100m']
LABELS = {'const':'Intercept','rd10':'R&D dependence · +10 percentage points',
          'pell10':'Pell dependence · +10 percentage points',
          'private':'Private nonprofit vs public','forprofit':'For-profit vs public',
          'landgrant':'Land grant','hbcu':'HBCU','doctoral':'Doctoral','aau':'AAU member',
          'hospital':'Hospital','medical':'Medical program','enroll1000':'FTE undergraduates · +1,000',
          'budget100m':'Budget · +$100 million (2022 dollars)'}

def records(d):
    return json.loads(d.to_json(orient='records',double_precision=8))

def aggregate(c):
    rows=[]
    for key,g in c.groupby('entity',sort=True):
        v=g[g.budget>0]
        modes=g.sector.mode()
        modal_sector=g.sort_values('year').loc[g.sector.isin(modes),'sector'].iloc[-1]
        r={'entity':key,'name':g['name'].iloc[-1],
           'sector':modal_sector, 'kind':g.kind.iloc[-1],
           'years':len(g), 'lobbied':g.lobbied.max(), 'spend':g.spend_real.mean(),
           'spend_nominal':g.spend.mean(),'budget':v.budget_real.mean(),
           'fteug':g.fteug.mean(),'rd':v.rd_real.sum()/v.budget_real.sum()*100 if len(v) else np.nan,
           'pell_pct':v.pell_real.sum()/v.budget_real.sum()*100 if len(v) else np.nan,
           'coverage':g.year.nunique(), 'imputed_share':g.imputed_spend.sum()/g.spend.sum() if g.spend.sum()>0 else 0}
        for f in FLAGS: r[f]=int(g[f].max())
        rows.append(r)
    return pd.DataFrame(rows)

def design(d,terms=TERMS,year=False):
    d=d.copy()
    d['rd10']=d.rd/10; d['pell10']=d.pell_pct/10
    d['private']=(d.sector=='Private').astype(int); d['forprofit']=(d.sector=='For-profit').astype(int)
    d['enroll1000']=d.fteug/1000; d['budget100m']=d.budget/1e8
    d=d.replace([np.inf,-np.inf],np.nan).dropna(subset=terms+['spend','lobbied'])
    terms=[t for t in terms if d[t].nunique()>1]
    X=sm.add_constant(d[terms].astype(float),has_constant='add')
    if year:
        X=pd.concat([X,pd.get_dummies(d.year.astype(int),prefix='year',drop_first=True,dtype=float)],axis=1)
    # Exclude exactly collinear columns and disclose them; do not fit a singular model.
    dropped=[]; keep=[]
    for col in X:
        if np.linalg.matrix_rank(X[keep+[col]].values)>len(keep): keep.append(col)
        else: dropped.append(col)
    return d,X[keep],dropped

def fit_models(d,spec,terms=TERMS,year=False,cluster=False):
    z,X,dropped=design(d,terms,year)
    results=[]
    for outcome in ['logit','ols']:
        meta={'spec':spec,'outcome':outcome,'n':len(z),'events':int(z.lobbied.sum()),
              'clusters':int(z.entity.nunique()),'dropped_collinear':dropped,
              'covariance':'cluster by entity' if cluster else ('HC0' if outcome=='logit' else 'HC3')}
        try:
            if len(z)<=X.shape[1]+2: raise ValueError('Insufficient residual degrees of freedom')
            model=sm.GLM(z.lobbied,X,family=sm.families.Binomial()) if outcome=='logit' else sm.OLS(z.spend,X)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                ordinary=model.fit()
                if cluster and outcome=='logit':
                    # Algebraically the usual one-way clustered sandwich. Compute the
                    # Bernoulli score as X*(y-p), avoiding GLM's 0/0 score at p=0 or 1.
                    robust=ordinary
                    fitted=np.asarray(ordinary.predict(X))
                    xv=X.to_numpy(); resid=np.asarray(z.lobbied)-fitted
                    bread=np.linalg.inv(xv.T@((fitted*(1-fitted))[:,None]*xv))
                    scores=pd.DataFrame(xv*resid[:,None]).groupby(z.entity.to_numpy()).sum().to_numpy()
                    G=len(scores); N,K=xv.shape
                    cov=bread@(scores.T@scores)@bread*(G/(G-1))*((N-1)/(N-K))
                    se=pd.Series(np.sqrt(np.diag(cov)),index=X.columns)
                    pv=pd.Series(2*stats.norm.sf(abs(ordinary.params/se)),index=X.columns)
                    ci=pd.DataFrame({0:ordinary.params-1.959963984540054*se,1:ordinary.params+1.959963984540054*se})
                    meta['covariance_implementation']='Bernoulli score sandwich; CR1 finite-sample correction; normal intervals'
                else:
                    robust=model.fit(cov_type='cluster',cov_kwds={'groups':z.entity}) if cluster else model.fit(cov_type=meta['covariance'])
                    se=robust.bse; pv=robust.pvalues; ci=robust.conf_int()
            meta['warnings']=list(dict.fromkeys(str(w.message) for w in caught))
            meta['condition_number']=float(np.linalg.cond(X))
            meta['rank']=int(np.linalg.matrix_rank(X)); meta['parameters']=len(X.columns)
            meta['converged']=bool(getattr(ordinary,'converged',True))
            if not meta['converged']: raise ValueError('Model did not converge')
            if outcome=='logit':
                p=ordinary.predict(X)
                meta['extreme_probabilities']=int(((p<1e-8)|(p>1-1e-8)).sum())
                meta['fit']=float(1-ordinary.llf/ordinary.llnull)
                # Perfect separation invalidates ordinary maximum-likelihood inference.
                if any('separation' in str(w.message).lower() for w in caught):
                    raise ValueError('Perfect separation: coefficients not reported')
            else: meta['fit']=float(ordinary.rsquared)
            if not np.isfinite(se).all(): raise ValueError('Nonfinite standard errors: inference not reported')
            for t in X:
                b=float(robust.params[t]); lo=float(ci.loc[t,0]); hi=float(ci.loc[t,1])
                results.append({**meta,'term':t,'label':LABELS.get(t,t),'beta':b,
                  'se':float(se[t]),'se_conventional':float(ordinary.bse[t]),
                  'p':float(pv[t]),'p_conventional':float(ordinary.pvalues[t]),
                  'lo':lo,'hi':hi,'effect':float(np.exp(b)) if outcome=='logit' else b,
                  'effect_lo':float(np.exp(np.clip(lo,-700,700))) if outcome=='logit' else lo,
                  'effect_hi':float(np.exp(np.clip(hi,-700,700))) if outcome=='logit' else hi})
            meta['status']='ok'
        except Exception as e:
            meta['status']='unavailable'; meta['reason']=str(e)
        diagnostics.append(meta)
    return results

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('csv'); args=ap.parse_args()
    OUT.mkdir(exist_ok=True); SITE.mkdir(parents=True,exist_ok=True)
    source=Path(args.csv); raw=pd.read_csv(source,low_memory=False)
    assert not raw.duplicated(['unit_id','year']).any()
    d=raw.copy(); d['entity']=d.system_group.astype(str)
    d['kind']=np.where(d.entity==d.unit_id.astype(str),'Standalone','System')
    d['lobbied']=pd.to_numeric(d.lobbied,errors='coerce')
    d['spend']=pd.to_numeric(d.lobbying_spend,errors='coerce')
    assert d.loc[d.lobbied==1,'spend'].notna().all()
    assert d.loc[d.lobbied==0,'spend'].isna().all()
    d.loc[d.lobbied==0,'spend']=0
    assert d.loc[d.lobbied.isna(),'spend'].isna().all()
    d['cpi_factor']=d.year.map(lambda y:CPI[2022]/CPI[y])
    # Recompute ratios from dollars; zeros in federal_rd are retained as supplied.
    d['rd']=np.where(d.budget>0,d.federal_rd/d.budget*100,np.nan)
    d['pell_pct']=np.where(d.budget>0,d.pell/d.budget*100,np.nan)
    d['imputed_spend']=np.where(d.lobbying_method=='imputed_by_enrollment_share',d.spend,0)
    d['imputed_n']=(d.lobbying_method=='imputed_by_enrollment_share').astype(int)
    rows=[]
    for (entity,yr),g in d.groupby(['entity','year'],sort=True):
        observed=g.lobbied.notna().all()
        row={'entity':entity,'year':int(yr),'name':g.unit_name.iloc[0] if g.kind.iloc[0]=='Standalone' else entity,
             'sector':g.sector.iloc[0],'kind':g.kind.iloc[0], 'campuses':len(g),
             'budget':g.budget.sum(),'federal_rd':g.federal_rd.sum(),'pell':g.pell.sum(),
             'fteug':g.fteug.sum(),'total_enrollment':g.total_enrollment.sum(),
             'lobbied':float(g.lobbied.max()) if observed else np.nan,
             'spend':float(g.spend.sum()) if observed else np.nan,
             'imputed_spend':float(g.imputed_spend.sum()) if observed else np.nan,
             'imputed_n':int(g.imputed_n.sum()),'budget_missing_campuses':int((~g.has_budget_data).sum()),
             'intl_pct':np.average(g.intl_pct,weights=g.total_enrollment) if g.total_enrollment.sum()>0 else 0}
        for f in FLAGS: row[f]=int(g[f].max())
        fac=CPI[2022]/CPI[yr]
        for base,new in [('budget','budget_real'),('federal_rd','rd_real'),('pell','pell_real'),('spend','spend_real')]: row[new]=row[base]*fac
        row['rd']=100*row['federal_rd']/row['budget'] if row['budget']>0 else np.nan
        row['pell_pct']=100*row['pell']/row['budget'] if row['budget']>0 else np.nan
        rows.append(row)
    annual=pd.DataFrame(rows)
    obs=annual[annual.lobbied.notna()].copy()
    cross=aggregate(obs)
    cross.to_csv(OUT/'entity_cross_section.csv',index=False)
    annual.to_csv(OUT/'entity_year_panel.csv',index=False)
    # Link changing reporting labels through stable campus IDs. This sensitivity
    # forms historical reporting families, not asserted present-day ownership.
    parent={e:e for e in obs.entity.unique()}
    def find(e):
        while parent[e]!=e:
            parent[e]=parent[parent[e]]; e=parent[e]
        return e
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    observed_campus=d[d.lobbied.notna()]
    for uid,g in observed_campus.groupby('unit_id'):
        keys=g.entity.unique()
        for other in keys[1:]: union(keys[0],other)
    mapping={e:find(e) for e in parent}
    pd.DataFrame({'source_group':list(mapping),'reporting_family':list(mapping.values())}).to_csv(OUT/'reporting_group_mapping.csv',index=False)
    changes=observed_campus.groupby('unit_id').filter(lambda g:g.entity.nunique()>1)
    changes[['unit_id','unit_name','year','entity']].to_csv(OUT/'identity_changes.csv',index=False)
    family_rows=[]
    for (family,yr),g in obs.assign(family=obs.entity.map(mapping)).groupby(['family','year']):
        r=g.iloc[-1].to_dict(); r['entity']=family
        for c in ['campuses','budget','budget_real','federal_rd','rd_real','pell','pell_real','fteug',
                  'total_enrollment','spend','spend_real','imputed_spend','imputed_n','budget_missing_campuses']:
            r[c]=g[c].sum()
        r['lobbied']=g.lobbied.max()
        for f in FLAGS:r[f]=g[f].max()
        family_rows.append(r)
    family_cross=aggregate(pd.DataFrame(family_rows))
    family_cross.to_csv(OUT/'stable_family_cross_section.csv',index=False)
    # Camp-style cross sections: all, standalone, systems; two outcomes each.
    diagnostics=[]; coef=[]
    for kind in ['All','Standalone','System']:
        subset=cross if kind=='All' else cross[cross.kind==kind]
        coef+=fit_models(subset,kind)
    # Annual extension with year indicators and clustered uncertainty.
    panel=obs.copy(); panel['budget']=panel.budget_real; panel['spend']=panel.spend_real
    for kind in ['All','Standalone','System']:
        coef+=fit_models(panel if kind=='All' else panel[panel.kind==kind],f'Panel {kind}',year=True,cluster=True)
    # Test the hypotheses within the intended sectors, rather than interpreting pooled main effects as sector effects.
    sector_terms=[t for t in TERMS if t not in ['private','forprofit']]
    coef+=fit_models(cross[cross.sector=='For-profit'],'H1 For-profit',terms=sector_terms)
    coef+=fit_models(cross[cross.sector!='For-profit'],'H2 Nonprofit',terms=[t for t in TERMS if t!='forprofit'])
    coef+=fit_models(cross[cross.rd.le(100)&cross.pell_pct.le(100)],'Ratios ≤100%')
    complete_keys=obs.loc[obs.budget_missing_campuses.eq(0)].groupby('entity').size()
    total_keys=obs.groupby('entity').size()
    complete=complete_keys[complete_keys.eq(total_keys.reindex(complete_keys.index))].index
    coef+=fit_models(cross[cross.entity.isin(complete)],'Complete campus budgets')
    # Alternative transparent temporal aggregation: mean of annual ratios.
    ratio_mean=cross.copy().set_index('entity')
    means=obs.groupby('entity')[['rd','pell_pct']].mean()
    ratio_mean[['rd','pell_pct']]=means
    coef+=fit_models(ratio_mean.reset_index(),'Mean annual ratios')
    coef+=fit_models(family_cross,'Stable reporting families')
    pd.DataFrame(coef).to_csv(OUT/'model_coefficients.csv',index=False)
    (OUT/'model_diagnostics.json').write_text(json.dumps(diagnostics,indent=2,allow_nan=False))
    desc=[]
    for kind in ['All','Standalone','System']:
        for sec in ['All','Public','Private','For-profit']:
            mask=pd.Series(True,index=cross.index)
            if kind!='All': mask &= cross.kind.eq(kind)
            if sec!='All': mask &= cross.sector.eq(sec)
            z=cross[mask]
            if len(z): desc.append({'kind':kind,'sector':sec,'n':len(z),'ever_lobbied_pct':100*z.lobbied.mean(),
              'mean_annual_spend_2022':z.spend.mean(),'median_annual_spend_2022':z.spend.median(),
              'budget_2022':z.budget.mean(),'fteug':z.fteug.mean(),'pell_dependence_pct':z.pell_pct.mean(),
              'rd_dependence_pct':z.rd.mean(),**{f:100*z[f].mean() for f in FLAGS}})
    pd.DataFrame(desc).to_csv(OUT/'descriptive_statistics.csv',index=False)
    status_desc=[]
    for label,z in [('All',cross),('Ever lobbied',cross[cross.lobbied==1]),('Never observed lobbying',cross[cross.lobbied==0])]:
        status_desc.append({'group':label,'n':len(z),'budget_2022':z.budget.mean(),'fteug':z.fteug.mean(),
          'mean_annual_spend_2022':z.spend.mean(),'pell_dependence_pct':z.pell_pct.mean(),
          'rd_dependence_pct':z.rd.mean(),**{f:100*z[f].mean() for f in FLAGS}})
    pd.DataFrame(status_desc).to_csv(OUT/'lobbyists_vs_nonlobbyists.csv',index=False)
    for variable,filename in [('pell_pct','top_pell_dependence.csv'),('rd','top_rd_dependence.csv'),('spend','top_lobbying_spenders.csv')]:
        cross.nlargest(10,variable).to_csv(OUT/filename,index=False)
    trends=obs.groupby(['year','sector']).agg(entities=('entity','size'),lobbyists=('lobbied','sum'),
      spend_nominal=('spend','sum'),spend_2022=('spend_real','sum')).reset_index()
    trends['participation_pct']=100*trends.lobbyists/trends.entities
    trends.to_csv(OUT/'annual_sector_trends.csv',index=False)
    correlations=[]
    for sector,term in [('For-profit','pell_pct'),('Nonprofit','rd')]:
        z=cross[(cross.sector=='For-profit') if sector=='For-profit' else (cross.sector!='For-profit')].dropna(subset=[term,'spend'])
        rho,p=stats.pearsonr(z[term],z.spend)
        correlations.append({'sector':sector,'term':term,'n':len(z),'pearson_r':float(rho),'p':float(p)})
    audit={'source_file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'source_rows':len(raw),'source_campuses':int(raw.unit_id.nunique()),'source_columns':list(raw.columns),
      'duplicate_campus_years':int(raw.duplicated(['unit_id','year']).sum()),
      'observed_rows':int(d.lobbied.notna().sum()),'pending_rows':int(d.lobbied.isna().sum()),
      'pending_years':sorted(d.loc[d.lobbied.isna(),'year'].unique().tolist()),
      'observed_years':sorted(d.loc[d.lobbied.notna(),'year'].unique().tolist()),
      'observed_campuses':int(d.loc[d.lobbied.notna(),'unit_id'].nunique()),
      'entity_count':len(cross),'systems':int(cross.kind.eq('System').sum()),
      'standalones':int(cross.kind.eq('Standalone').sum()),'ever_lobbied':int(cross.lobbied.sum()),
      'invalid_campus_budgets_observed':int(((d.budget<=0)&d.lobbied.notna()).sum()),
      'invalid_entity_budgets_observed':int(obs.budget.le(0).sum()),
      'cross_missing_finance':int(cross.budget.isna().sum()),
      'campus_rd_zero_ratio_blank':int(((raw.federal_rd==0)&raw.rd_dependence_pct.isna()).sum()),
      'cross_ratios_above_100':int((cross.rd.gt(100)|cross.pell_pct.gt(100)).sum()),
      'observed_imputed_rows':int(((d.imputed_n==1)&d.lobbied.notna()).sum()),
      'observed_imputed_spend_share':float(d.imputed_spend.sum()/d.spend.sum()),
      'sector_changers':int(obs.groupby('entity').sector.nunique().gt(1).sum()),
      'campuses_with_group_changes':int(changes.unit_id.nunique()),
      'stable_reporting_families':len(family_cross),
      'source_overlap_example':{'year':2015,'direct_unit_id':170976,'direct_spend':295000,
        'allocated_unit_ids':[171137,171146],'allocated_spend_total':295000,
        'status':'Potential overlapping filing: requires validation against original lobbying reports; retained as supplied.'},
      'nominal_spend_total':float(obs.spend.sum()),'real_spend_total':float(obs.spend_real.sum()),
      'cpi':CPI,'cpi_url':CPI_URL,'correlations':correlations}
    assert np.isclose(obs.spend.sum(),d.spend.sum())
    assert len(obs)==obs[['entity','year']].drop_duplicates().shape[0]
    for yr in audit['observed_years']:
        assert np.isclose(obs.loc[obs.year==yr,'spend'].sum(),d.loc[d.year==yr,'spend'].sum())
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2))
    # Compact, finite, columnar browser data. Pending values are JSON null, never zero.
    cols=['entity','year','name','sector','kind','campuses','budget','budget_real','rd_real','pell_real',
      'fteug','lobbied','spend','spend_real','rd','pell_pct','imputed_n','imputed_spend',
      'budget_missing_campuses']+FLAGS
    payload={'columns':cols,'rows':json.loads(annual[cols].to_json(orient='values',double_precision=5)),
      'models':json.loads(pd.DataFrame(coef).to_json(orient='records',double_precision=9)),
      'diagnostics':diagnostics,'audit':audit,'descriptive':desc}
    (SITE/'data.json').write_text(json.dumps(payload,separators=(',',':'),allow_nan=False))
    print(json.dumps(audit,indent=2))
    print(pd.DataFrame(diagnostics)[['spec','outcome','n','status']].to_string(index=False))
