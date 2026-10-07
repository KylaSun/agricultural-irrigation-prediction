# -*- coding: utf-8 -*-
# 中文教学说明见同名 notebook。
# 初始化独立研究环境，固定特征、参数和输出目录。
from pathlib import Path
import os, json, hashlib, platform, time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (precision_score, recall_score, f1_score,
    balanced_accuracy_score, confusion_matrix, average_precision_score,
    precision_recall_curve, auc)
from IPython.display import display

# 可以用环境变量切换项目位置；默认从当前目录向上查找。
def v1_find_root():
    if os.environ.get('IRRIGATION_PROJECT_ROOT'):
        return Path(os.environ['IRRIGATION_PROJECT_ROOT']).resolve()
    for p in [Path.cwd(), *Path.cwd().parents]:
        if (p/'data/merged/dataset_zone_1.csv').exists(): return p
    p = Path('/Users/kaylasun/Downloads/low-cost-irrigation')
    if (p/'data/merged/dataset_zone_1.csv').exists(): return p
    raise FileNotFoundError('请设置 IRRIGATION_PROJECT_ROOT 为 low-cost-irrigation 文件夹')
v1_root = v1_find_root()
v1_out = Path(os.environ.get('RESEARCH_OUTPUT_DIR', str(v1_root/'outputs/research_core_v1')))
v1_out.mkdir(parents=True, exist_ok=True)
v1_started = time.time()
v1_weather = ['weather_temp','weather_humidity','weather_rain','weather_pressure','weather_wind_speed','weather_radiation']
v1_configs = {
    'C1 Soil-only': ['soil_moisture'],
    'C2 Low-cost hybrid': ['soil_moisture'] + v1_weather,
    'C3 Sensor-rich': ['soil_moisture'] + v1_weather + ['soil_temperature_0-7cm','soil_temperature_7-18cm','ec','ph','water_vol_past_4h']}
v1_all = v1_configs['C3 Sensor-rich']
v1_thresholds = {1:40,2:40,3:60,4:80,5:50}
v1_rf_params = dict(n_estimators=200, class_weight='balanced', min_samples_leaf=5, random_state=42, n_jobs=2)
v1_seeds = [101, 202, 303, 404, 505]
v1_rates = [0., .1, .3, .5, .7]
def v1_save(frame, name):
    frame.to_csv(v1_out/(name+'.csv'), index=False)
    return frame
print('项目:', v1_root, '\n输出:', v1_out)

# 按配置逐项记录信息来源，避免把特征数误当硬件数。
v1_source = {f:'历史天气再分析（非实时预报）' for f in v1_weather}
v1_source.update({'soil_moisture':'现场土壤相对湿度探头（非通用体积含水率）',
 'soil_temperature_0-7cm':'历史天气服务土温', 'soil_temperature_7-18cm':'历史天气服务土温，实际 band 7–28cm',
 'ec':'现场 EC 探头', 'ph':'现场 pH 探头','water_vol_past_4h':'执行器事件 × 分区额定流量；重建过去4h'})
v1_config_table = v1_save(pd.DataFrame([
    {'configuration':c,'n_features':len(fs),'feature':f,'source':v1_source[f],
     'field_sensor_masked':f in ['soil_moisture','ec','ph']} for c,fs in v1_configs.items() for f in fs
]),'sensor_configuration')
display(v1_config_table)

# 核验历史CSV标签与清洗后第144行的关系。
v1_legacy_dir = v1_root/'Soil Moisture, Irrigation Actuator and Weather Dat/02_processed_data/preprocessed'
v1_legacy_frames, v1_legacy_audit = [], []
for z, threshold in v1_thresholds.items():
    p = pd.read_csv(v1_legacy_dir/f'dataset_zone_{z}_preprocessed.csv', parse_dates=['ts']).sort_values('ts')
    assert not p.ts.duplicated().any()
    future_rows = p.soil_moisture.shift(-144)
    hours = (p.ts.shift(-144)-p.ts).dt.total_seconds()/3600
    by_clock = p.set_index('ts').soil_moisture.reindex(p.ts+pd.Timedelta(hours=24)).to_numpy()
    known = np.isfinite(by_clock)
    v1_legacy_audit.append({'zone':z,'rows':len(p),'target_missing':int(p.target_point_24h.isna().sum()),
        'row144_comparable':int(future_rows.notna().sum()),
        'row144_value_matches':int(np.isclose(future_rows,p.target_point_24h).sum()),
        'clock24_comparable':int(known.sum()),'clock24_value_matches':int(np.isclose(by_clock,p.target_point_24h).sum()),
        'row144_horizon_median_hours':hours.median(),'row144_horizon_max_hours':hours.max(),
        'row144_horizon_over24_share':(hours.dropna()>24).mean()})
    p['zone']=z
    # 缺标签不能强制变为 0；旧文件此次虽无缺失，仍明确处理。
    p=p[p.target_point_24h.notna()].copy()
    p['future_dry']=(p.target_point_24h<threshold).astype(int)
    for f,lo,hi in [('ec',0,1000),('ph',3,9)]: p[f]=p[f].where(p[f].between(lo,hi))
    v1_legacy_frames.append(p)
v1_legacy = pd.concat(v1_legacy_frames, ignore_index=True)
v1_legacy_train = v1_legacy[v1_legacy.ts.between('2025-03-01','2025-05-31 23:59:59')].copy()
v1_legacy_test = v1_legacy[v1_legacy.ts.between('2025-06-01','2025-07-31 23:59:59')].copy()
display(v1_save(pd.DataFrame(v1_legacy_audit),'legacy_target_audit'))
display(v1_save(pd.DataFrame([{'split':n,'n':len(d),'positive':int(d.future_dry.sum()),'positive_rate':d.future_dry.mean()}
    for n,d in [('train_sensing',v1_legacy_train),('test_sensing',v1_legacy_test)]]),'legacy_split_audit'))

# 从原始合并层构建精确24小时标签，保留共同样本并检查时间隔离。
v1_frames, v1_quality, v1_hashes = [], [], {}
v1_flatline_rows=[]
for z, threshold in v1_thresholds.items():
    path=v1_root/f'data/merged/dataset_zone_{z}.csv'
    v1_hashes[str(path.relative_to(v1_root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    raw=pd.read_csv(path,parse_dates=['ts']).sort_values('ts')
    assert not raw.ts.duplicated().any(), '重复时间戳必须先审计'
    utc=raw.ts.dt.tz_localize('Europe/Rome',nonexistent='NaT',ambiguous='NaT').dt.tz_convert('UTC')
    invalid_time=int(utc.isna().sum())
    d=raw.loc[utc.notna()].copy()
    d.index=pd.DatetimeIndex(utc[utc.notna()]); d=d.drop(columns='ts')
    d=d.reindex(pd.date_range(d.index.min(),d.index.max(),freq='10min'))
    for f,lo,hi in [('soil_moisture',0,115),('ec',0,1000),('ph',3,9)]:
        d[f]=pd.to_numeric(d[f],errors='coerce').where(d[f].between(lo,hi))
    d['soil_moisture']=d.soil_moisture.clip(upper=100)
    # 按已观测的过去识别长时不变序列；不读取未来来修正当前输入。
    obs=d.soil_moisture.dropna()
    groups=obs.ne(obs.shift()).cumsum()
    starts=pd.Series(obs.index,index=obs.index).groupby(groups).transform('first')
    elapsed=pd.Series(obs.index,index=obs.index)-starts
    count=obs.groupby(groups).cumcount()+1
    stalled=(elapsed>=pd.Timedelta(hours=24))&(count>=12)
    suspect_index=obs.index[stalled]
    d['soil_flatline_flag']=d.index.isin(suspect_index)
    for month,g in d.groupby(d.index.tz_convert('Europe/Rome').strftime('%Y-%m')):
        v1_flatline_rows.append({'zone':z,'month':month,'valid_before_flatline':int(g.soil_moisture.notna().sum()),
            'flagged':int(g.soil_flatline_flag.sum()),'unique_before_flatline':g.soil_moisture.nunique()})
    d.loc[d.soil_flatline_flag,'soil_moisture']=np.nan
    # 窗口右闭：t-3h50min 至 t 共24个10分钟 bin，不含未来。
    d['water_vol_past_4h']=(d.irrigation_duration_minutes*(.4 if z==5 else 1.1)).rolling('4h',min_periods=24).sum()
    d['target_moisture_24h']=d.soil_moisture.reindex(d.index+pd.Timedelta(hours=24)).to_numpy()
    d['decision_ts']=d.index+pd.Timedelta(minutes=10)
    d['target_ts']=d.decision_ts+pd.Timedelta(hours=24)
    d['local_ts']=d.index.tz_convert('Europe/Rome')
    d['zone']=z; d['threshold']=threshold
    d['sample_id']=[f'{z}|{t.isoformat()}' for t in d.index]
    v1_quality.append({'zone':z,'raw_rows':len(raw),'grid_rows':len(d),'invalid_local_times':invalid_time,
        'valid_current_soil':int(d.soil_moisture.notna().sum()),'valid_target':int(d.target_moisture_24h.notna().sum())})
    d=d.loc[d.target_moisture_24h.notna()].copy()
    d['future_dry']=(d.target_moisture_24h<threshold).astype(int)
    v1_frames.append(d.reset_index(drop=True))
v1_master=pd.concat(v1_frames,ignore_index=True).sort_values(['decision_ts','zone']).set_index('sample_id',drop=False)
assert v1_master.index.is_unique
assert ((v1_master.target_ts-v1_master.decision_ts)==pd.Timedelta(hours=24)).all()
assert not v1_master[v1_all].isin([np.inf,-np.inf]).any().any()
def v1_period(start,end):
    a=pd.Timestamp(start,tz='Europe/Rome').tz_convert('UTC')
    b=pd.Timestamp(end,tz='Europe/Rome').tz_convert('UTC')
    return v1_master.loc[(v1_master.decision_ts>=a)&(v1_master.decision_ts<b)&(v1_master.target_ts<b)].copy()
v1_train=v1_period('2025-03-01','2025-06-01')
v1_test=v1_period('2025-06-01','2025-08-01')
assert v1_train.target_ts.max()<v1_test.decision_ts.min()
assert set(v1_train.index).isdisjoint(v1_test.index)
assert v1_train.future_dry.nunique()==v1_test.future_dry.nunique()==2
v1_save(v1_master.reset_index(drop=True),'master_dataset')
v1_save(pd.DataFrame(v1_quality),'data_quality')
v1_save(pd.DataFrame(v1_flatline_rows),'flatline_quality_audit')
v1_split_table=v1_save(pd.DataFrame([{'split':s,'zone':z,'n':len(g),'positive':int(g.future_dry.sum()),
 'positive_rate':g.future_dry.mean(),'first_decision':g.decision_ts.min(),'last_decision':g.decision_ts.max(),
 'last_target':g.target_ts.max(),'complete_case_n':int(g[v1_all].notna().all(axis=1).sum())}
 for s,d in [('train',v1_train),('test',v1_test)] for z,g in d.groupby('zone')]),'split_audit')
v1_availability=v1_save(pd.DataFrame([{'split':s,'feature':f,'available_rate':d[f].notna().mean()}
 for s,d in [('train',v1_train),('test',v1_test)] for f in v1_all]),'feature_availability')
v1_fair_rows=[]
for c,fs in v1_configs.items():
    for s,d in [('train',v1_train),('test',v1_test)]:
        x=d[fs]; y=d.future_dry
        assert x.index.equals(y.index)
        v1_fair_rows.append({'configuration':c,'split':s,'n':len(x),
          'samples_sha256':hashlib.sha256('\n'.join(x.index).encode()).hexdigest(),
          'target_sha256':hashlib.sha256(y.to_numpy().tobytes()).hexdigest(),
          'algorithm':'median+missing indicator; RF200 balanced leaf5 seed42',
          'evaluation':'fixed 0.5 threshold; unified v1_evaluate'})
v1_fair=v1_save(pd.DataFrame(v1_fair_rows),'fair_comparison_audit')
for _,g in v1_fair.groupby('split'):
    assert g.samples_sha256.nunique()==g.target_sha256.nunique()==1
display(v1_split_table); display(v1_fair)
print('六项公平性通过：相同标签/日期/样本/切分/算法/评价。原始缺失率另见 feature_availability.csv。')

# 统一指标定义，检查混淆矩阵方向与单类边界。
def v1_evaluate(y, probability):
    y=np.asarray(y,dtype=int); p=np.asarray(probability,dtype=float)
    assert len(y)==len(p)>0 and np.isin(y,[0,1]).all()
    assert np.isfinite(p).all() and ((p>=0)&(p<=1)).all()
    pred=(p>=.5).astype(int)
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    both=len(np.unique(y))==2
    if both:
        precision,recall,_=precision_recall_curve(y,p)
        area=auc(recall,precision); ap=average_precision_score(y,p)
    else: area=ap=np.nan
    return dict(n=len(y),positive=int(y.sum()),positive_rate=y.mean(),
      Precision=precision_score(y,pred,zero_division=0),
      Recall=recall_score(y,pred,zero_division=0) if y.sum() else np.nan,
      F1=f1_score(y,pred,zero_division=0) if y.sum() else np.nan,
      Balanced_Accuracy=balanced_accuracy_score(y,pred) if both else np.nan,
      PR_AUC=area,Average_Precision=ap,predicted_positive_rate=pred.mean(),
      TN=int(tn),FP=int(fp),FN=int(fn),TP=int(tp))
def v1_model():
    return Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                     ('rf',RandomForestClassifier(**v1_rf_params))])
def v1_probability(model,x):
    classes=model.named_steps['rf'].classes_
    return model.predict_proba(x)[:,list(classes).index(1)] if 1 in classes else np.zeros(len(x))
# 这些检查针对常见误用：矩阵方向、概率计算和单类评价。
check=v1_evaluate([0,0,1,1],[.1,.8,.2,.9])
assert [check[k] for k in ['TN','FP','FN','TP']]==[1,1,1,1]
assert check['F1']==.5 and check['Balanced_Accuracy']==.5
assert np.isnan(v1_evaluate([0,0],[.1,.9])['PR_AUC'])
assert v1_evaluate([0,1],[.1,.9])['Average_Precision']==1
print('统一评价边界检查通过。')

# 在相同样本上训练同一算法，补充简单参照和完整样本敏感性。
v1_models={}; v1_rows=[]; v1_predictions=[]
for c,fs in v1_configs.items():
    model=v1_model().fit(v1_train[fs],v1_train.future_dry)
    v1_models[c]=model
    p=v1_probability(model,v1_test[fs])
    v1_rows.append({'configuration':c,**v1_evaluate(v1_test.future_dry,p)})
    pred=v1_test[['sample_id','zone','decision_ts','future_dry']].copy()
    pred['configuration']=c; pred['probability']=p; pred['prediction']=(p>=.5).astype(int)
    v1_predictions.append(pred)
v1_ablation=v1_save(pd.DataFrame(v1_rows),'sensor_ablation')
v1_pred=pd.concat(v1_predictions,ignore_index=True)
v1_save(v1_pred,'test_predictions')
base=np.full(len(v1_test),v1_train.future_dry.mean())
persist=np.where(v1_test.soil_moisture.notna(),(v1_test.soil_moisture<v1_test.threshold).astype(float),base)
v1_baselines=v1_save(pd.DataFrame([{'configuration':name,**v1_evaluate(v1_test.future_dry,p)}
 for name,p in [('Train-prevalence constant',base),('Current-state persistence',persist)]]),'reference_baselines')
v1_save(pd.DataFrame([{'configuration':c,'zone':z,**v1_evaluate(g.future_dry,g.probability)}
 for (c,z),g in v1_pred.groupby(['configuration','zone'])]),'zone_results')
v1_cc_train=v1_train.dropna(subset=v1_all); v1_cc_test=v1_test.dropna(subset=v1_all)
v1_cc_rows=[]
for c,fs in v1_configs.items():
    if len(v1_cc_train)>0 and len(v1_cc_test)>0 and v1_cc_train.future_dry.nunique()==2:
        model=v1_model().fit(v1_cc_train[fs],v1_cc_train.future_dry)
        v1_cc_rows.append({'configuration':c,'status':'complete common samples',**v1_evaluate(v1_cc_test.future_dry,v1_probability(model,v1_cc_test[fs]))})
    else: v1_cc_rows.append({'configuration':c,'status':'insufficient classes/samples'})
v1_save(pd.DataFrame(v1_cc_rows),'complete_case_sensitivity')
v1_legacy_rows=[]
for c,fs in v1_configs.items():
    model=Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('rf',RandomForestClassifier(**v1_rf_params))])
    model.fit(v1_legacy_train[fs],v1_legacy_train.future_dry)
    v1_legacy_rows.append({'configuration':c,**v1_evaluate(v1_legacy_test.future_dry,v1_probability(model,v1_legacy_test[fs]))})
v1_save(pd.DataFrame(v1_legacy_rows),'legacy_ablation_rerun')
display(v1_ablation.round(4)); display(v1_baselines.round(4)); display(pd.DataFrame(v1_cc_rows).round(4))

# 固定共享随机掩码，重复两类缺失情境，验证零缺失一致。
v1_field=['soil_moisture','ec','ph']
v1_missing_rows=[]; v1_mask_audit=[]
for seed in v1_seeds:
    rng=np.random.default_rng(seed)
    # 列顺序和行顺序固定，所有配置从同一份遮挡表选列。
    utrain=pd.DataFrame(rng.random((len(v1_train),len(v1_field))),index=v1_train.index,columns=v1_field)
    utest=pd.DataFrame(rng.random((len(v1_test),len(v1_field))),index=v1_test.index,columns=v1_field)
    for rate in v1_rates:
        xtr=v1_train[v1_all].copy(); xte=v1_test[v1_all].copy()
        for split,x,u in [('train',xtr,utrain),('test',xte,utest)]:
            for f in v1_field:
                observed=x[f].notna(); mask=u[f]<rate
                v1_mask_audit.append({'seed':seed,'rate':rate,'split':split,'feature':f,
                    'observed_before':int(observed.sum()),'newly_masked':int((observed&mask).sum()),
                    'realized_additional_rate':(observed&mask).sum()/observed.sum() if observed.sum() else np.nan})
                x.loc[mask,f]=np.nan
        for c,fs in v1_configs.items():
            for scenario in ['train_and_test','test_only']:
                if rate==0 or scenario=='test_only': model=v1_models[c]
                else: model=v1_model().fit(xtr[fs],v1_train.future_dry)
                result=v1_evaluate(v1_test.future_dry,v1_probability(model,xte[fs]))
                v1_missing_rows.append({'configuration':c,'scenario':scenario,'seed':seed,'rate':rate,**result})
        print('完成 mask seed',seed,'缺失',rate,flush=True)
v1_missing=v1_save(pd.DataFrame(v1_missing_rows),'missingness_repetitions')
assert not v1_missing.duplicated(['configuration','scenario','seed','rate']).any()
for c in v1_configs:
    zero=v1_missing[(v1_missing.configuration==c)&(v1_missing.rate==0)]
    ref=v1_ablation.set_index('configuration').loc[c]
    for metric in ['F1','Balanced_Accuracy','PR_AUC','Average_Precision','TN','FP','FN','TP']:
        assert np.allclose(zero[metric],ref[metric],equal_nan=True)
v1_save(pd.DataFrame(v1_mask_audit),'missingness_mask_audit')
v1_summary=v1_missing.groupby(['configuration','scenario','rate'])[['Precision','Recall','F1','Balanced_Accuracy','PR_AUC','Average_Precision','predicted_positive_rate']].agg(['mean','std']).reset_index()
v1_summary.columns=['_'.join(filter(None,col)) if isinstance(col,tuple) else col for col in v1_summary.columns]
v1_save(v1_summary,'missingness_summary')
display(v1_summary.round(4))

# 冻结模型，逐月和逐区检查时间分布变化。
v1_temporal_rows=[]; v1_temporal_zones=[]
for start,end in [('2025-06-01','2025-07-01'),('2025-07-01','2025-08-01'),('2025-08-01','2025-09-01'),('2025-09-01','2025-10-01')]:
    d=v1_period(start,end)
    if len(d)==0:
        v1_temporal_rows.append({'month':start[:7],'status':'no eligible targets'}); continue
    for c,fs in v1_configs.items():
        p=v1_probability(v1_models[c],d[fs])
        v1_temporal_rows.append({'month':start[:7],'configuration':c,'status':'frozen March-May model',**v1_evaluate(d.future_dry,p)})
        for z in sorted(d.zone.unique()):
            mask=(d.zone==z).to_numpy()
            v1_temporal_zones.append({'month':start[:7],'zone':z,'configuration':c,**v1_evaluate(d.future_dry.to_numpy()[mask],p[mask])})
v1_temporal=v1_save(pd.DataFrame(v1_temporal_rows),'temporal_robustness')
v1_save(pd.DataFrame(v1_temporal_zones),'temporal_by_zone')
display(v1_temporal.round(4))

# 将实际指标保存成表图和中文结论，记录参数与数据来源。
plt.style.use('seaborn-v0_8-whitegrid')
v1_colors=['#2463a6','#e38d2c','#28936b']
fig,ax=plt.subplots(figsize=(9,4.5))
v1_ablation.set_index('configuration')[['F1','Balanced_Accuracy','Average_Precision']].plot.bar(ax=ax,color=v1_colors,rot=0)
ax.set_ylim(0,1); ax.set_title('Fixed 24-hour target: matched-sample ablation'); ax.set_ylabel('Score'); ax.set_xlabel('')
fig.tight_layout(); fig.savefig(v1_out/'ablation.png',dpi=160); plt.show()
fig,axes=plt.subplots(1,3,figsize=(11,3.5))
for ax,(_,r) in zip(axes,v1_ablation.iterrows()):
    cm=np.array([[r.TN,r.FP],[r.FN,r.TP]],dtype=int)
    ax.imshow(cm,cmap='Blues'); ax.set_title(r.configuration)
    ax.set_xticks([0,1],['Not dry','Dry']); ax.set_yticks([0,1],['Not dry','Dry'])
    ax.set_xlabel('Predicted'); ax.set_ylabel('Observed')
    for (i,j),v in np.ndenumerate(cm): ax.text(j,i,str(v),ha='center',va='center',color='white' if v>cm.max()/2 else 'black')
fig.tight_layout(); fig.savefig(v1_out/'confusion_matrices.png',dpi=160); plt.show()
fig,axes=plt.subplots(2,2,figsize=(11,8),sharex=True)
for row,scenario in enumerate(['train_and_test','test_only']):
    for col,metric in enumerate(['F1','Balanced_Accuracy']):
        ax=axes[row,col]
        for color,c in zip(v1_colors,v1_configs):
            g=v1_summary[(v1_summary.configuration==c)&(v1_summary.scenario==scenario)].sort_values('rate')
            ax.errorbar(g.rate*100,g[metric+'_mean'],yerr=g[metric+'_std'],marker='o',capsize=3,label=c,color=color)
        ax.set_title(scenario+' | '+metric); ax.set_ylim(0,1); ax.set_ylabel('Mean +/- mask SD'); ax.set_xlabel('Additional field-sensor missingness (%)')
axes[0,0].legend(fontsize=8); fig.tight_layout(); fig.savefig(v1_out/'missingness.png',dpi=160); plt.show()
fig,ax=plt.subplots(figsize=(9,4.5))
for color,c in zip(v1_colors,v1_configs):
    g=v1_temporal[v1_temporal.configuration==c]
    ax.plot(g.month,g.Balanced_Accuracy,marker='o',color=color,label=c)
ax.axhline(.5,color='gray',linestyle='--'); ax.set_ylim(0,1); ax.set_xticks(range(4), ['2025-06','2025-07','2025-08','2025-09']); ax.set_xlim(-.1,3.1); ax.text(3,.35,'Single class\nBA undefined',ha='center'); ax.set_title('Frozen March-May model: monthly evaluation'); ax.set_ylabel('Balanced accuracy'); ax.legend()
fig.tight_layout(); fig.savefig(v1_out/'temporal.png',dpi=160); plt.show()
v1_manifest={'protocol':'Research Technical Core v1','source_hashes':v1_hashes,
 'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
 'configs':v1_configs,'rf_params':v1_rf_params,'mask_seeds':v1_seeds,'mask_rates':v1_rates,
 'masked_features':v1_field,'target':'range-valid observed soil_moisture at decision+24 elapsed hours < zone threshold',
 'thresholds':v1_thresholds,'timezone':'Europe/Rome converted to UTC; nonexistent/ambiguous timestamps dropped',
 'train':'March-May; target before June 1','test':'June-July; target before August 1',
 'selection':'target available; same rows per configuration; input missingness imputed using training median',
 'flatline_rule':'same valid observed value for >=24h and >=12 observations; flag from detection onward, causal',
 'caveat':'Historical weather reanalysis/interpolation; retrospective research, not deployment validation',
 'elapsed_seconds':round(time.time()-v1_started,2)}
(v1_out/'run_manifest.json').write_text(json.dumps(v1_manifest,ensure_ascii=False,indent=2))
v1_known=[]
for _,r in v1_baselines.iterrows():
    v1_known.append(f"- 参照 {r.configuration}: F1={r.F1:.3f}, Balanced Accuracy={r.Balanced_Accuracy:.3f}, AP={r.Average_Precision:.3f}。")
for _,r in v1_ablation.iterrows():
    v1_known.append(f"- {r.configuration}: F1={r.F1:.3f}, Balanced Accuracy={r.Balanced_Accuracy:.3f}, AP={r.Average_Precision:.3f}, 预测正例率={r.predicted_positive_rate:.1%}。")
v1_report="""# Research Technical Core v1 — 实际运行结论

## Known（已核验）
- 旧 target 与清洗后后移144行一致；不能普遍解释为24小时。旧缺失曲线重复追加，不是两轮独立实验。
- 新核心以 UTC 精确24小时匹配有效观测标签，所有配置共享样本与标签；训练边界 purge，填补器仅 fit 训练数据。
"""+f'- 正式训练 {len(v1_train):,} 行，测试 {len(v1_test):,} 行；正例率分别 {v1_train.future_dry.mean():.1%}、{v1_test.future_dry.mean():.1%}。\n'+'\n'.join(v1_known)+"""

## Not Known（尚不能回答）
- 中国试点的阈值、灌溉时长、水量、节水收益、产量与作物安全效果。
- 哪个单独新增 feature 导致 C3 变化；需要后续逐项消融才能归因。
- 实际硬件成本与稳定性；尚未验证 BOM、设备通讯、真实连续故障。
- 跨农场、跨年泛化；历史结果不等于在线天气可用条件下的表现。

## Limitations（研究边界）
- 单农场、单季、分区阈值不同，RF 不输入 zone；标签是相对探头尺度，不等于通用含水率或缺水真值。
- 标签仅在未来传感器可用时存在，结果条件于该可用性；完整样本子集也有选择偏差。
- 范围过滤和因果24h不变值筛查仍不能排除所有漂移/尖峰，flatline筛查也可能误伤真实稳定状态；flatline_quality_audit.csv 记录剔除数量。时间聚合与历史天气插值不能证明在线因果可用性。
- 历史灌溉干预影响未来湿度，预测并非反事实灌溉需求。
- 10分钟样本和跨区天气高度相关；五次遮挡 SD 不是泛化置信区间，MCAR 不代表持续断网/MNAR。
- 主时间划分沿用既有研究探索，测试曾被查看；本版不调参，但不能称首次未见的独立验证。
- C3 混合天气服务、现场探头和操作日志；特征数量不是硬件数量或成本。
- 新旧数据清洗、目标、purge、mask定义均有变化，新旧分数变化不能单独归因于一个改动。

## 独立重跑
打开 research_core_v1.ipynb，重启内核后 Run All；或在项目内运行 src/research_core_v1.py。
依赖版本、源文件 SHA256、实验参数在 run_manifest.json；表格为 CSV，图为 PNG。
先核对 split_audit 和 fair_comparison_audit，再读 sensor_ablation/reference_baselines，最后读 missingness_summary 和 temporal_robustness。
本版完成的是可独立重跑的离线研究核心；硬件、Demo 与真实试点仍是后续工作。
"""
(v1_out/'Known_NotKnown_Limitations.md').write_text(v1_report)
print(v1_report)