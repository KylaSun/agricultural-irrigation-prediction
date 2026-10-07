from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, balanced_accuracy_score
project=Path('/Users/kaylasun/Downloads/low-cost-irrigation')
out=Path('/Users/kaylasun/Documents/Codex/2026-10-07/referenced-chatgpt-conversation-this-is-an/outputs/results')
data_dir=project/'outputs/research_core_v1'
pred=pd.read_csv(data_dir/'test_predictions.csv')
master=pd.read_csv(data_dir/'master_dataset.csv',usecols=['sample_id','local_ts','soil_moisture','threshold'])
test=pred[pred.configuration=='C1 Soil-only'].merge(master,on='sample_id',validate='one_to_one')
test['day']=test.local_ts.str[:10]
train=pd.read_csv(data_dir/'split_audit.csv')
train=train[train.split=='train']
prevalence=train.positive.sum()/train.n.sum()
test['persistence_pred']=np.where(test.soil_moisture.notna(),(test.soil_moisture<test.threshold).astype(int),(prevalence>=.5).astype(int))
# 把三种模型预测与同一批样本及简单参照对齐。
wide=test[['sample_id','zone','day','future_dry','persistence_pred']]
wide=wide.merge(pred.pivot(index='sample_id',columns='configuration',values='prediction').reset_index(),on='sample_id',validate='one_to_one')
wide=wide.rename(columns={'persistence_pred':'Current-state persistence'})
def score(y,p):
 return {'F1':f1_score(y,p,zero_division=0),'Balanced_Accuracy':balanced_accuracy_score(y,p)}
rows=[]
for zone,g in wide.groupby('zone'):
 for config in ['C1 Soil-only','C2 Low-cost hybrid','C3 Sensor-rich']:
  rows.append({'scope':f'Zone {zone}','configuration':config,'n':len(g),'positive':int(g.future_dry.sum()),'positive_rate':g.future_dry.mean(),**score(g.future_dry,g[config])})
 rows.append({'scope':f'Zone {zone}','configuration':'Current-state persistence','n':len(g),'positive':int(g.future_dry.sum()),'positive_rate':g.future_dry.mean(),**score(g.future_dry,g['Current-state persistence'])})
for config in ['C1 Soil-only','C2 Low-cost hybrid','C3 Sensor-rich','Current-state persistence']:
 rows.append({'scope':'Pooled all zones','configuration':config,'n':len(wide),'positive':int(wide.future_dry.sum()),'positive_rate':wide.future_dry.mean(),**score(wide.future_dry,wide[config])})
by_zone=pd.DataFrame(rows)
by_zone.to_csv(out/'model_vs_persistence_by_zone.csv',index=False)
# 以当地日期为单位，每次抽取连续7天区块；同一天的全部 zone 一起抽，保留时间聚集结构。
days=sorted(wide.day.unique());by_day={d:wide.index[wide.day.eq(d)].to_numpy() for d in days}
rng=np.random.default_rng(20261007);B=2000;block=7
pairs=[('C1 Soil-only','Current-state persistence','C1 - persistence'),
       ('C2 Low-cost hybrid','Current-state persistence','C2 - persistence'),
       ('C3 Sensor-rich','Current-state persistence','C3 - persistence'),
       ('C2 Low-cost hybrid','C1 Soil-only','C2 - C1')]
boot=[]
for b in range(B):
 chosen=[]
 while len(chosen)<len(days):
  start=int(rng.integers(0,len(days)))
  chosen.extend(days[(start+j)%len(days)] for j in range(block))
 sample=np.concatenate([by_day[d] for d in chosen[:len(days)]])
 g=wide.iloc[sample];y=g.future_dry.to_numpy()
 for left,right,label in pairs:
  ls=score(y,g[left].to_numpy());rs=score(y,g[right].to_numpy())
  boot.append({'replicate':b,'comparison':label,'metric':'F1','difference':ls['F1']-rs['F1']})
  boot.append({'replicate':b,'comparison':label,'metric':'Balanced_Accuracy','difference':ls['Balanced_Accuracy']-rs['Balanced_Accuracy']})
draws=pd.DataFrame(boot)
summary=(draws.groupby(['comparison','metric']).difference.agg(
 mean='mean',lower=lambda s:s.quantile(.025),upper=lambda s:s.quantile(.975),
 fraction_positive=lambda s:(s>0).mean()).reset_index())
summary.to_csv(out/'model_comparison_block_bootstrap.csv',index=False)
print('测试期：',len(days),'天；',len(wide),'行；训练正例率回退值：',round(prevalence,4))
print('分区结果：');print(by_zone.round(4).to_string(index=False))
print('7天区块配对重抽样：');print(summary.round(4).to_string(index=False))
print('说明：95%分位区间是探索性不确定性范围，不是独立农场验证或正式显著性检验。')
