"""Independent comparison reporting; does not import or modify strategy engines."""
import argparse
import base64
import hashlib
import html
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
COLORS = ['#176b87', '#e38b36']

def load(path, column):
    df = pd.read_csv(path)
    if not df.columns.is_unique or not {'Index', column} <= set(df.columns):
        raise ValueError('Required unique date/return columns missing: ' + str(path))
    dates = pd.to_datetime(df['Index'], errors='coerce')
    raw = df[column]
    values = pd.to_numeric(raw, errors='coerce')
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError('Invalid or duplicate dates: ' + str(path))
    if (raw.notna() & values.isna()).any() or np.isinf(values).any() or (values <= -1).any():
        raise ValueError('Invalid simple returns (must be decimals and greater than -1).')
    return pd.Series(values.to_numpy(), index=dates, name=column).sort_index()

def metrics(r, ann=252):
    wealth = (1 + r).cumprod()
    # Include initial capital in the running peak, including a first-day loss.
    dd = wealth / wealth.cummax().clip(lower=1) - 1
    cagr = np.expm1(np.log1p(r).sum() * ann / len(r))
    vol = r.std(ddof=1) * np.sqrt(ann)
    mdd = dd.min()
    return {'CAGR': cagr, 'Annualized volatility': vol,
            'Sharpe (rf=0)': r.mean() * ann / vol if vol > 0 else np.nan,
            'Maximum drawdown': mdd,
            'Calmar': cagr / abs(mdd) if mdd < 0 else np.nan,
            'Cumulative return': wealth.iloc[-1] - 1,
            'Positive days': (r > 0).mean()}

def figure(frame, title, ylabel, percent=False, bars=False):
    fig, ax = plt.subplots(figsize=(11, 4.3), layout='constrained')
    fig.patch.set_facecolor('#ffffff')
    if bars:
        frame.plot.bar(ax=ax, color=COLORS, width=.75, rot=45)
    else:
        for i, col in enumerate(frame):
            ax.plot(frame.index, frame[col], label=col, color=COLORS[i], linewidth=1.65)
    ax.set_title(title, loc='left', fontsize=14, pad=14)
    ax.set_ylabel(ylabel)
    ax.set_xlabel('')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', alpha=.18)
    ax.legend(frameon=False)
    if percent:
        ax.yaxis.set_major_formatter(PercentFormatter(1))
    return fig

def save_figure(fig, folder, name):
    fig.savefig(folder / (name + '.png'), dpi=180)
    fig.savefig(folder / (name + '.svg'))
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    return '<img alt="' + html.escape(name.replace('_', ' ')) + '" src="data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode() + '">'

PERIODS = [('Full available period', '2016-01-01', None),
           ('2016–2022', '2016-01-01', '2022-12-31'),
           ('Post Covid: 2023–present', '2023-01-01', None)]


def period_metrics(frame, annualization=252):
    result = {}
    for col in frame:
        r = frame[col]
        if len(r) < 2 or r.isna().any():
            result[col] = {key: np.nan for key in metrics(pd.Series([0., 0.]), annualization)}
        else:
            result[col] = metrics(r, annualization)
    return pd.DataFrame(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--top-down', required=True, type=Path)
    p.add_argument('--bottom-up', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    args = p.parse_args()
    if args.output_dir.exists():
        p.error('Use a new output directory.')
    a = load(args.top_down, 'Top_Down_Total_Portfolio').rename('Top-Down')
    b = load(args.bottom_up, 'Bottom_Up_Total_Portfolio').rename('Bottom-Up')
    data = pd.concat([a, b], axis=1).sort_index()
    # Begin at first date where both runners have begun reporting performance.
    if a.first_valid_index() is None or b.first_valid_index() is None:
        raise ValueError('Both strategies require constructed performance observations.')
    first = max(a.first_valid_index(), b.first_valid_index(), pd.Timestamp('2016-01-01'))
    last = min(a.index.max(), b.index.max())
    data = data.loc[first:last]
    if data.empty:
        raise ValueError('No overlapping performance period from 2016.')
    if data.isna().any().any():
        raise ValueError('Missing interior portfolio returns; rerun the current Bottom-Up runner. No dates are dropped or portfolio returns filled.')
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=False)
    sections, summaries, checks = [], [], []
    for i, (label, start, end) in enumerate(PERIODS):
        frame = data.loc[start:end].copy()
        if frame.empty:
            sections.append(f'<h2>{html.escape(label)}</h2><p>No available observations.</p>')
            continue
        prefix = 'Full_Period' if i == 0 else f'Period_{i}'
        summary = period_metrics(frame)
        summaries.append(pd.concat({label: summary}, names=['Period', 'Metric']))
        summary.to_csv(out / f'{prefix}_Performance.csv', index_label='Metric')
        frame.to_csv(out / f'{prefix}_Returns.csv', index_label='Index')
        # No missing values are skipped, dropped, or filled, even in compounding.
        wealth = (1 + frame).cumprod(skipna=False)
        dd = wealth / wealth.cummax(skipna=False).clip(lower=1) - 1
        annual_rows = []
        for year, group in frame.groupby(frame.index.year):
            annual_rows.append({'Year': year, **{c: np.nan if group[c].isna().any()
                else (1 + group[c]).prod() - 1 for c in frame}})
        annual = pd.DataFrame(annual_rows).set_index('Year')
        annual.to_csv(out / f'{prefix}_Annual_Returns.csv')
        pretty = summary.astype(object)
        for metric in summary.index:
            for c in frame:
                v = summary.loc[metric, c]
                pretty.loc[metric, c] = 'N/A' if pd.isna(v) else (f'{v:.2f}' if metric in ['Sharpe (rf=0)', 'Calmar'] else f'{v:.2%}')
        year_table = annual.map(lambda v: 'N/A' if pd.isna(v) else f'{v:.2%}')
        base = pd.DataFrame([[1., 1.]], index=[frame.index[0] - pd.Timedelta(days=1)], columns=frame.columns)
        images = [save_figure(figure(pd.concat([base, wealth]) * 100, f'{label} | Growth of 100', 'Wealth index'), out, f'{prefix}_Growth'),
                  save_figure(figure(dd, f'{label} | Drawdown', 'Drawdown', True), out, f'{prefix}_Drawdown'),
                  save_figure(figure(annual, f'{label} | Annual return', 'Return', True, True), out, f'{prefix}_Annual')]
        checks.append({'period': label, 'start': str(frame.index.min().date()), 'end': str(frame.index.max().date()),
                       'rows': len(frame), 'missing_returns': frame.isna().sum().to_dict(), 'rows_removed_within_period': 0})
        sections.append(f'''<section><h2>{html.escape(label)}</h2><p>{frame.index.min().date()} – {frame.index.max().date()}</p>
<div class="scroll">{pretty.to_html(border=0)}</div>{images[0]}{images[1]}{images[2]}
<h3>Annual returns</h3><div class="scroll">{year_table.to_html(border=0)}</div></section>''')
    pd.concat(summaries).to_csv(out / 'Performance_By_Period.csv')
    sources = [{'path': str(f.resolve()), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
               for f in (args.top_down, args.bottom_up)]
    (out / 'Validation.json').write_text(json.dumps({'periods': checks, 'sources': sources,
        'policy': 'No within-period deletion, filling or alteration; incomplete metrics are N/A.'}, indent=2))
    body = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agawa | Comparison by period</title><style>body{font:16px/1.6 system-ui;background:#f3f6f8;color:#21313d;margin:0}main{max-width:1100px;margin:auto;padding:32px 24px}section{background:white;padding:24px;margin:24px 0;border-radius:12px}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:right}th:first-child{text-align:left}.scroll{overflow:auto}small{overflow-wrap:anywhere}</style><main>
<p>CONFIDENTIAL · LOCAL REPORT</p><h1>Top-Down vs Bottom-Up — full period and subperiods</h1>
<p>Full available period, 2016–2022, and Post Covid: 2023–latest available date. Full-period growth and drawdown run continuously across the 2022/2023 boundary; subperiods restart their own capital and peaks. Performance begins when both strategy runners first report returns.</p>
<p>Source returns are preserved. No rows within the selected periods are removed and no missing returns are replaced with zero. N/A means the period contains a missing return or the ratio is undefined. A cumulative path stops at its first missing value; a later point is not connected across that gap.</p>'''
    body += '<section><h2>Daily-return convention</h2><p>Both runners use zero for missing raw instrument returns during realized daily aggregation, while retaining all other instrument contributions. This assumes no price change for the missing instrument; it does not recover missing market data. Estimation windows still use complete observations. Weights are fixed daily capital weights within each quarter, implying constant-mix returns rather than buy-and-hold drift. Costs and financing are not added. Some node-level target risk budgets require further review; optimizer success alone does not establish exact risk-budget attainment.</p></section>'
    body += ''.join(sections)
    body += '''<h2>Calculation notes</h2><p>CAGR uses 252 observations per year. Volatility uses daily sample standard deviation × √252. Sharpe assumes a zero risk-free rate. Maximum drawdown includes initial capital in the peak. Calmar is CAGR / absolute maximum drawdown. Annual returns compound only if that year's selected period is complete; boundary years may be partial. Costs, financing and currency conversion are not added. No strategy recommendation is inferred from unavailable metrics.</p>
<details><summary>Local sources</summary>'''
    body += ''.join('<p><small>' + html.escape(s['path']) + '<br>SHA-256: ' + s['sha256'] + '</small></p>' for s in sources)
    body += '</details></main></html>'
    (out / 'Strategy_Comparison.html').write_text(body, encoding='utf-8')
    print('Comparison report saved locally. No portfolio values printed.')

