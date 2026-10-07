from pathlib import Path
import pandas as pd,numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import *
root=Path('/Users/kaylasun/Downloads/low-cost-irrigation')
out=root/'outputs/research_core_v1'
weather=['weather_temp','weather_humidity','weather_rain','weather_pressure','weather_wind_speed','weather_radiation']
cfg={'C1 Soil-only':['soil_moisture'],'C2 Low-cost hybrid':['soil_moisture']+weather,'C3 Sensor-rich':['soil_moisture']+weather+['soil_temperature_0-7cm','soil_temperature_7-18cm','ec','ph','water_vol_past_4h']}
thresholds={1:40,2:40,3:60,4:80,5:50}
def load(screen):
 frames=[];qc=[]
 for z,threshold in thresholds.items():
  d=pd.read_csv(root/f'data/merged/dataset_zone_{z}.csv',parse_dates=['ts']).sort_values('ts')
  u=d.ts.dt.tz_localize('Europe/Rome',nonexistent='NaT',ambiguous='NaT').dt.tz_convert('UTC')
  d=d.loc[u.notna()].copy();d.index=pd.DatetimeIndex(u[u.notna()]);d=d.drop(columns='ts')
  d=d.reindex(pd.date_range(d.index.min(),d.index.max(),freq='10min'))
  for f,lo,hi in [('soil_moisture',0,115),('ec',0,1000),('ph',3,9)]:d[f]=pd.to_numeric(d[f],errors='coerce').where(d[f].between(lo,hi))
  d.soil_moisture=d.soil_moisture.clip(upper=100)
  v=d.soil_moisture.dropna();g=v.ne(v.shift()).cumsum()
  starts=pd.Series(v.index,index=v.index).groupby(g).transform('first')
  flag=v.index[((pd.Series(v.index,index=v.index)-starts>=pd.Timedelta(hours=24))&(v.groupby(g).cumcount()+1>=12))]
  qc.append({'zone':z,'screen':screen,'flagged':len(flag)})
  if screen=='range_plus_flatline':d.loc[flag,'soil_moisture']=np.nan
  d['water_vol_past_4h']=(d.irrigation_duration_minutes*(.4 if z==5 else 1.1)).rolling('4h',min_periods=24).sum()
  d['future']=d.soil_moisture.reindex(d.index+pd.Timedelta(hours=24)).to_numpy()
  d['decision']=d.index+pd.Timedelta(minutes=10);d['end']=d.decision+pd.Timedelta(hours=24)
  d['zone']=z;d['y']=(d.future<threshold).astype('Int64');d.loc[d.future.isna(),'y']=pd.NA
  d['id']=[f'{z}|{t.isoformat()}' for t in d.index]
  frames.append(d.reset_index(drop=True))
 return pd.concat(frames,ignore_index=True),qc
def period(d,start,end):
 a=pd.Timestamp(start,tz='Europe/Rome').tz_convert('UTC');b=pd.Timestamp(end,tz='Europe/Rome').tz_convert('UTC')
 return d[(d.decision>=a)&(d.decision<b)&(d.end<b)&d.y.notna()].copy()
r,rq=load('range_only');f,fq=load('range_plus_flatline')
rt,ft=period(r,'2025-06-01','2025-08-01'),period(f,'2025-06-01','2025-08-01')
ids=sorted(set(rt.id)&set(ft.id));rt=rt.set_index('id').loc[ids];ft=ft.set_index('id').loc[ids]
assert rt.y.astype(int).equals(ft.y.astype(int))
rows=[]
for name,data in [('range_only',r),('range_plus_flatline',f)]:
 tr=period(data,'2025-03-01','2025-06-01').sort_values(['decision','zone'])
 te=rt if name=='range_only' else ft
 for c,features in cfg.items():
  model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),RandomForestClassifier(n_estimators=200,class_weight='balanced',min_samples_leaf=5,random_state=42,n_jobs=2))
  model.fit(tr[features],tr.y.astype(int));p=model.predict_proba(te[features])[:,list(model[-1].classes_).index(1)]
  y=rt.y.astype(int).to_numpy();yp=(p>=.5);tn,fp,fn,tp=confusion_matrix(y,yp,labels=[0,1]).ravel()
  rows.append({'screen':name,'configuration':c,'train_n':len(tr),'common_test_n':len(ids),'positive_rate':y.mean(),'F1':f1_score(y,yp),'balanced_accuracy':balanced_accuracy_score(y,yp),'AP':average_precision_score(y,p),'TN':tn,'FP':fp,'FN':fn,'TP':tp})
pd.DataFrame(rq+fq).to_csv(out/'flatline_rule_sensitivity_by_zone.csv',index=False)
result=pd.DataFrame(rows);result.to_csv(out/'flatline_rule_sensitivity.csv',index=False)
print('Shared test rows:',len(ids),'same labels:',rt.y.astype(int).equals(ft.y.astype(int)))
print('Flagged readings by zone');print(pd.DataFrame(rq+fq).pivot(index='zone',columns='screen',values='flagged'))
print(result.round(4).to_string(index=False))
