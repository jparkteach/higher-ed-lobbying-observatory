"""Independent numerical and data-integrity checks for the replication outputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'output'
audit=json.loads((OUT/'audit.json').read_text())
co=pd.read_csv(OUT/'model_coefficients.csv'); annual=pd.read_csv(OUT/'entity_year_panel.csv')
cross=pd.read_csv(OUT/'entity_cross_section.csv'); diagnostics=json.loads((OUT/'model_diagnostics.json').read_text())
checks=[]
def check(condition,label):
    if not condition: raise AssertionError(label)
    checks.append(label)
check(not annual.duplicated(['entity','year']).any(),'Unique reporting-group/year keys')
check(annual.loc[annual.year.ge(2023),'lobbied'].isna().all(),'Pending outcomes remain missing')
check(annual.loc[annual.year.ge(2023),'spend'].isna().all(),'Pending spending remains missing')
check(annual.loc[annual.lobbied.eq(0),'spend'].eq(0).all(),'Confirmed nonlobbyists have zero spending')
check(np.isclose(annual.spend.sum(),audit['nominal_spend_total']),'Nominal spending reconciles with source audit')
check(np.isclose(annual.spend_real.sum(),audit['real_spend_total']),'Constant-dollar spending reconciles')
check(all(r['status']=='ok' and r['converged'] and r['rank']==r['parameters'] for r in diagnostics),'All 24 models converge with full-rank design matrices')
check(np.isfinite(co[['beta','se','p','lo','hi','effect','effect_lo','effect_hi']]).all().all(),'All exported estimates and uncertainty are finite')
check((co.lo<=co.beta).all() and (co.hi>=co.beta).all(),'All intervals bracket their point estimates')
check(int(co.loc[co.spec.eq('All'),'n'].iloc[0])==len(cross)-audit['cross_missing_finance'],'Main model exclusions reconcile to missing finances')

def matrix(d):
    X=pd.DataFrame({'const':1.0,'rd10':d.rd/10,'pell10':d.pell_pct/10,
      'private':d.sector.eq('Private').astype(float),'forprofit':d.sector.eq('For-profit').astype(float)},index=d.index)
    for term in ['landgrant','hbcu','doctoral','aau','hospital','medical']:X[term]=d[term].astype(float)
    X['enroll1000']=d.fteug/1000;X['budget100m']=d.budget/1e8
    return X

z=cross.dropna(subset=['budget','rd','pell_pct']);X=matrix(z)
# Independently solve the linear normal problem, without statsmodels OLS.
b=np.linalg.lstsq(X.to_numpy(),z.spend.to_numpy(),rcond=None)[0]
expected=co[(co.spec=='All')&(co.outcome=='ols')].set_index('term').loc[X.columns]
check(np.allclose(b,expected.beta,rtol=1e-9,atol=1e-5),'OLS agrees with NumPy least squares')
# Fit a discrete Logit model rather than the GLM used in the analysis.
fit=sm.Logit(z.lobbied,X).fit(disp=False,maxiter=200,cov_type='HC0')
expected=co[(co.spec=='All')&(co.outcome=='logit')].set_index('term').loc[X.columns]
check(np.allclose(fit.params,expected.beta,rtol=1e-7,atol=1e-7),'Binomial GLM agrees with independent Logit coefficients')
check(np.allclose(fit.bse,expected.se,rtol=1e-6,atol=1e-8),'Cross-sectional robust logit uncertainty agrees')
# Validate the explicitly implemented stable Bernoulli cluster covariance against
# statsmodels' discrete Logit score/Hessian implementation.
z=annual[annual.lobbied.notna() & annual.budget.gt(0)].copy()
z['budget']=z.budget_real;z['spend']=z.spend_real;X=matrix(z)
X=pd.concat([X,pd.get_dummies(z.year.astype(int),prefix='year',drop_first=True,dtype=float)],axis=1)
fit=sm.Logit(z.lobbied,X).fit(disp=False,maxiter=200,cov_type='cluster',cov_kwds={'groups':z.entity})
expected=co[(co.spec=='Panel All')&(co.outcome=='logit')].set_index('term').loc[X.columns]
check(np.allclose(fit.params,expected.beta,rtol=1e-6,atol=1e-7),'Annual logistic estimates agree with independent Logit')
check(np.allclose(fit.bse,expected.se,rtol=1e-6,atol=1e-7),'Manual Bernoulli clustered sandwich agrees with statsmodels Logit clustering')

data=json.loads((ROOT/'docs/data.json').read_text())
browser=pd.DataFrame(data['rows'],columns=data['columns'])
check(len(browser)==len(annual),'Dashboard includes every reporting-group/year record')
check(browser[browser.year.ge(2023)].lobbied.isna().all(),'Dashboard serializes pending outcomes as null')
check(np.isclose(browser.spend.sum(),annual.spend.sum(),atol=.01),'Dashboard values reconcile with analysis tables')
summary={'status':'passed','checks':checks,'models':len(diagnostics),'coefficients':len(co),
  'limitations':['Source filing deduplication and selection criteria not independently validated.',
                 'Dashboard interaction and layout checks are recorded separately in the task.']}
(OUT/'verification.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
