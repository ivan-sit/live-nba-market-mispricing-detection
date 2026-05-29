// Build slides/final_deck.pptx via pptxgenjs
// Run from repo root:  node slides/build.js
// 14 slides, 10 min, navy/ocean palette, Georgia titles + Calibri body.

const PptxGenJS = require("pptxgenjs");
const pres = new PptxGenJS();
pres.layout = "LAYOUT_WIDE";       // 13.33" x 7.5"
pres.title = "Live NBA Market Mispricing Detection";
pres.author = "Ming Yin Ivan Sit & Vishnu Manathattai";
pres.company = "UCLA STATS 211";

const C = { NAVY:"0B2545", DEEP:"13315C", TEAL:"1C7293", SKY:"8DA9C4",
            CREAM:"F6F6F2", ACCENT:"EEA02B", INK:"1A1A1A", WHITE:"FFFFFF" };
const F = { title:"Georgia", body:"Calibri", code:"Courier New" };

function header(s, title, subtitle) {
  s.background = { color: C.WHITE };
  s.addText(title, { x:0.55, y:0.28, w:12.3, h:0.85,
    fontFace:F.title, fontSize:28, bold:true, color:C.NAVY });
  if (subtitle) s.addText(subtitle, { x:0.55, y:1.05, w:12.3, h:0.4,
    fontFace:F.body, fontSize:14, italic:true, color:C.DEEP });
  s.addShape("line", { x:0.55, y:1.45, w:12.3, h:0, line:{color:C.TEAL, width:2} });
}
function footer(s, n) {
  s.addText("STATS 211 · NBA Mispricing · Sit & Manathattai",
    { x:0.55, y:7.1, w:8, h:0.3, fontFace:F.body, fontSize:10, color:C.SKY });
  s.addText(String(n), { x:12.45, y:7.1, w:0.45, h:0.3,
    fontFace:F.body, fontSize:10, color:C.SKY, align:"right" });
}

const builders = [];

// ─── 1. TITLE ─────────────────────────────────────────────────────────────
builders.push(s => {
  s.background = { color: C.NAVY };
  s.addText("Live NBA Market Mispricing Detection",
    { x:0.6, y:2.2, w:12.1, h:1.2, fontFace:F.title, fontSize:42, bold:true, color:C.CREAM });
  s.addText("A behavioral asset-pricing test of crowd miscalibration",
    { x:0.6, y:3.45, w:12.1, h:0.6, fontFace:F.title, fontSize:22, italic:true, color:C.SKY });
  s.addShape("rect", { x:0.6, y:4.25, w:3.5, h:0.08, fill:{color:C.ACCENT}, line:{color:C.ACCENT,width:0} });
  s.addText("Ming Yin Ivan Sit · Vishnu Manathattai",
    { x:0.6, y:4.5, w:12.1, h:0.5, fontFace:F.body, fontSize:18, color:C.CREAM });
  s.addText("STATS 211 · Prof. Xiaowu Dai · Spring 2026",
    { x:0.6, y:5.05, w:12.1, h:0.4, fontFace:F.body, fontSize:14, color:C.SKY });
});

// ─── 2. TRANSITION (1/2) — Halawi to live markets · 30s ───────────────────
builders.push(s => {
  header(s, "From Halawi to live markets", "Midterm → final · the bridge (30 sec)");
  s.addText([
    { text:"Midterm result, one line: ", options:{ bold:true } },
    { text:"Halawi et al. (NeurIPS 2024) showed LMs approach the crowd on forecasting Brier (0.179 vs 0.149) — and the buried gem is that a " },
    { text:"4:1 LM + crowd aggregate beats either alone.", options:{ bold:true, color:C.ACCENT } },
  ], { x:0.55, y:1.7, w:12.3, h:1.2, fontFace:F.body, fontSize:18, color:C.INK });
  s.addText([
    { text:"The deeper observation: ", options:{ bold:true } },
    { text:"both are miscalibrated, in opposite directions. " },
    { text:"LMs hedge", options:{ italic:true, color:C.DEEP } },
    { text:" (RLHF). " },
    { text:"Crowds overreact", options:{ italic:true, color:C.DEEP } },
    { text:" (Moskowitz 2021, Ötting 2022)." },
  ], { x:0.55, y:3.0, w:12.3, h:1.0, fontFace:F.body, fontSize:18, color:C.INK });
  s.addShape("roundRect", { x:0.55, y:4.3, w:12.3, h:2.1,
    fill:{color:C.CREAM}, line:{color:C.TEAL, width:1.5}, rectRadius:0.1 });
  s.addText("So the question:", { x:0.85, y:4.45, w:11.7, h:0.4,
    fontFace:F.body, fontSize:14, italic:true, color:C.DEEP });
  s.addText("Where can we cleanly test the claim that a calibrated model beats the crowd — with fast resolution, real money, and a documented bias?",
    { x:0.85, y:4.85, w:11.7, h:1.45, fontFace:F.title, fontSize:21, italic:true, color:C.NAVY });
});

// ─── 3. TRANSITION (2/2) — Why NBA, not crypto · 30s ──────────────────────
builders.push(s => {
  header(s, "Why NBA, not crypto", "End of transition · the rest is NBA (30 sec)");
  const rows = [
    [{ text:"", options:{ fill:C.NAVY }},
     { text:"NBA in-play", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }},
     { text:"Crypto 5-min lead-lag", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }}],
    [{ text:"Ground truth", options:{ bold:true, color:C.NAVY, fill:C.CREAM }},
     { text:"every state → outcome\ncalibration problem", options:{ color:C.INK }},
     { text:"proxy labels\nstat-arb on noisy data", options:{ color:C.INK }}],
    [{ text:"Literature", options:{ bold:true, color:C.NAVY, fill:C.CREAM }},
     { text:"Moskowitz 2021 (J. Finance) —\npositive result", options:{ color:C.NAVY, bold:true }},
     { text:"Sifat et al. 2019 —\n'barely exploitable' (negative)", options:{ color:C.INK }}],
    [{ text:"Legal venue (CA)", options:{ bold:true, color:C.NAVY, fill:C.CREAM }},
     { text:"Kalshi NBA event contracts\n(CFTC-regulated)", options:{ color:C.NAVY, bold:true }},
     { text:"—", options:{ color:C.INK, align:"center" }}],
    [{ text:"Sample", options:{ bold:true, color:C.NAVY, fill:C.CREAM }},
     { text:"~1,230 games × hundreds of ticks", options:{ color:C.INK }},
     { text:"thinner per-event", options:{ color:C.INK }}],
  ];
  s.addTable(rows, { x:0.55, y:1.7, w:12.3, colW:[3.0, 4.65, 4.65],
    fontFace:F.body, fontSize:14, border:{ type:"solid", color:C.SKY, pt:1 }, rowH:0.7 });
  s.addText("Trade with the literature, not against it, on the venue we can actually use.",
    { x:0.55, y:6.3, w:12.3, h:0.5, fontFace:F.title, fontSize:18, italic:true, color:C.DEEP, align:"center" });
});

// ─── 4. RESEARCH QUESTION ────────────────────────────────────────────────
builders.push(s => {
  header(s, "Research question", "Pre-registered before any test-set data was touched");
  s.addShape("roundRect", { x:0.55, y:1.75, w:12.3, h:1.85,
    fill:{color:C.CREAM}, line:{color:C.TEAL, width:1.5}, rectRadius:0.1 });
  s.addText("Can a calibrated in-game NBA win-probability model systematically identify live-market mispricings driven by crowd overreaction — specifically in trailing-team scoring events?",
    { x:0.85, y:1.95, w:11.7, h:1.5, fontFace:F.title, fontSize:20, italic:true, color:C.NAVY });
  s.addText("Two pre-registered tests:",
    { x:0.55, y:3.95, w:12.3, h:0.4, fontFace:F.body, fontSize:16, bold:true, color:C.DEEP });
  s.addText([
    { text:"H1 (primary)", options:{ bold:true, color:C.ACCENT }},
    { text:" — trailing team in 10–15 pt deficit hits a made FG → market over-shifts vs structural model." },
  ], { x:0.85, y:4.45, w:12.0, h:0.7, fontFace:F.body, fontSize:16, color:C.INK });
  s.addText([
    { text:"H4 (secondary)", options:{ bold:true, color:C.ACCENT }},
    { text:" — trailing team in ≥10 pt deficit hits a made 3-pointer → larger over-shift." },
  ], { x:0.85, y:5.15, w:12.0, h:0.7, fontFace:F.body, fontSize:16, color:C.INK });
  s.addText("Block-bootstrap by game (n = games, not ticks). Holm-Bonferroni across the pre-registered set.",
    { x:0.55, y:6.2, w:12.3, h:0.5, fontFace:F.body, fontSize:13, italic:true, color:C.SKY });
});

// ─── 5. DATA ──────────────────────────────────────────────────────────────
builders.push(s => {
  header(s, "Data", "Pipeline foundations");
  const items = [
    ["Play-by-play",                "nba_api · free",         "2,460 games · 2023-24 + 2024-25 regular seasons"],
    ["Live sportsbook odds",        "the-odds-api · free",    "9 books · in-play game-winner moneyline"],
    ["Kalshi 1H-winner contracts",  "Kalshi public API · free","peer-driven · CFTC-regulated"],
    ["Per-minute snapshots",        "derived (1st half)",     "59,040 rows × 4 features"],
  ];
  const rows = [[
    { text:"Source",   options:{ bold:true, color:C.CREAM, fill:C.NAVY }},
    { text:"Origin",   options:{ bold:true, color:C.CREAM, fill:C.NAVY }},
    { text:"Coverage", options:{ bold:true, color:C.CREAM, fill:C.NAVY }},
  ]];
  items.forEach(r => rows.push(r.map((c,i) => ({
    text:c, options: i===0 ? { bold:true, color:C.NAVY } : { color:C.INK }
  }))));
  s.addTable(rows, { x:0.55, y:1.7, w:12.3, fontFace:F.body, fontSize:14,
    border:{ type:"solid", color:C.SKY, pt:1 }, rowH:0.7 });
  s.addText("Splits: train on 2023-24 · held-out test on 2024-25 (touched once at the end).",
    { x:0.55, y:6.2, w:12.3, h:0.4, fontFace:F.body, fontSize:14, italic:true, color:C.DEEP });
});

// ─── 6. MODEL V2 ──────────────────────────────────────────────────────────
builders.push(s => {
  header(s, "The model (V2)", "Simple, interpretable, defensible");
  s.addText([
    { text:"XGBoost ", options:{ bold:true, color:C.NAVY }},
    { text:"on 4 features: " },
    { text:"minute_idx, score_diff_home, recent_run_diff, period.", options:{ italic:true, color:C.DEEP, fontFace:F.code }},
  ], { x:0.55, y:1.7, w:12.3, h:0.7, fontFace:F.body, fontSize:18, color:C.INK });
  s.addText([
    { text:"Isotonic calibration ", options:{ bold:true, color:C.NAVY }},
    { text:"on a held-out fold — wraps raw probabilities so 0.70 means 70% empirically." },
  ], { x:0.55, y:2.45, w:12.3, h:0.7, fontFace:F.body, fontSize:18, color:C.INK });
  s.addText([
    { text:"Ablation: ", options:{ bold:true, color:C.NAVY }},
    { text:"engineered features (leverage, possession proxy, " },
    { text:"score_diff × time_remaining", options:{ italic:true, fontFace:F.code }},
    { text:") " },
    { text:"did not improve Brier", options:{ bold:true, color:C.ACCENT }},
    { text:" by the 0.005 threshold → kept simple." },
  ], { x:0.55, y:3.2, w:12.3, h:1.0, fontFace:F.body, fontSize:18, color:C.INK });
  s.addShape("roundRect", { x:0.55, y:4.7, w:12.3, h:1.8,
    fill:{color:C.CREAM}, line:{color:C.SKY, width:1}, rectRadius:0.1 });
  s.addText("Why simple is right for a 3-page paper:",
    { x:0.85, y:4.85, w:12.0, h:0.45, fontFace:F.body, fontSize:15, italic:true, color:C.DEEP });
  s.addText("Every choice defensible. No overfitting story. Brier-comparable to published in-game WP models (Bashuk; Lopez & Matthews).",
    { x:0.85, y:5.35, w:12.0, h:1.1, fontFace:F.body, fontSize:17, color:C.INK });
});

// ─── 7. CALIBRATION RESULT (headline #1) ─────────────────────────────────
builders.push(s => {
  header(s, "Calibration result · out-of-sample 2024-25", "Headline figure #1");
  function tile(x, label, value, sub) {
    s.addShape("roundRect", { x, y:1.8, w:3.9, h:2.0, fill:{color:C.NAVY}, line:{color:C.NAVY,width:0}, rectRadius:0.12 });
    s.addText(label, { x, y:1.9, w:3.9, h:0.5, fontFace:F.body, fontSize:14, color:C.SKY, align:"center" });
    s.addText(value, { x, y:2.4, w:3.9, h:1.0, fontFace:F.title, fontSize:54, bold:true, color:C.CREAM, align:"center" });
    s.addText(sub, { x, y:3.4, w:3.9, h:0.4, fontFace:F.body, fontSize:13, italic:true, color:C.ACCENT, align:"center" });
  }
  tile(0.55, "Brier (lower better)", "0.149", "well-calibrated");
  tile(4.7,  "ECE",                  "0.008", "near-zero miscalibration");
  tile(8.85, "Held-out sample",      "1,230", "games · 2024-25");
  s.addText("Reliability diagram (predicted vs empirical probability):",
    { x:0.55, y:4.15, w:12.3, h:0.4, fontFace:F.body, fontSize:14, italic:true, color:C.DEEP });
  s.addShape("roundRect", { x:0.55, y:4.6, w:12.3, h:1.95,
    fill:{color:C.CREAM}, line:{color:C.SKY, width:1}, rectRadius:0.1 });
  s.addText("[ reliability diagram — predicted-vs-empirical falls on the diagonal across deciles ]",
    { x:0.55, y:5.35, w:12.3, h:0.5, fontFace:F.body, fontSize:14, italic:true, color:C.SKY, align:"center" });
  s.addText("The probabilities can be trusted.",
    { x:0.55, y:6.65, w:12.3, h:0.35, fontFace:F.title, fontSize:18, italic:true, bold:true, color:C.NAVY, align:"center" });
});

// ─── 8. MISPRICING V5 (headline #2) ──────────────────────────────────────
builders.push(s => {
  header(s, "Mispricing thesis (V5) · pre-registered tests", "Headline figure #2 · held-out 2024-25");
  const rows = [
    [{ text:"Test", options:{ bold:true, color:C.CREAM, fill:C.NAVY }},
     { text:"n (events / games)", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }},
     { text:"Structural shift for scorer", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }},
     { text:"p-value", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }}],
    [{ text:"H1 — trailing 10–15, made FG", options:{ bold:true, color:C.NAVY }},
     { text:"4,596 / 947", options:{ align:"center", color:C.INK }},
     { text:"+0.0075  [+0.005, +0.010]", options:{ align:"center", color:C.ACCENT, bold:true }},
     { text:"< 0.0001", options:{ align:"center", color:C.ACCENT, bold:true }}],
    [{ text:"H4 — trailing ≥10, made 3PT", options:{ bold:true, color:C.NAVY }},
     { text:"2,162 / 780", options:{ align:"center", color:C.INK }},
     { text:"+0.0138  [+0.011, +0.017]", options:{ align:"center", color:C.ACCENT, bold:true }},
     { text:"< 0.0001", options:{ align:"center", color:C.ACCENT, bold:true }}],
  ];
  s.addTable(rows, { x:0.55, y:1.7, w:12.3, colW:[4.2, 2.1, 4.0, 2.0],
    fontFace:F.body, fontSize:15, border:{ type:"solid", color:C.SKY, pt:1 }, rowH:0.9 });
  s.addText("Block-bootstrap by game (10,000 resamples). Holm-Bonferroni across the pre-registered set.",
    { x:0.55, y:4.55, w:12.3, h:0.4, fontFace:F.body, fontSize:13, italic:true, color:C.SKY });
  s.addShape("roundRect", { x:0.55, y:5.05, w:12.3, h:1.8,
    fill:{color:C.CREAM}, line:{color:C.TEAL, width:1.5}, rectRadius:0.1 });
  s.addText("A trailing team's basket shifts the calibrated model in their favor by ~0.7–1.4 points over the next 60 seconds.",
    { x:0.85, y:5.2, w:11.7, h:0.7, fontFace:F.body, fontSize:16, color:C.INK });
  s.addText("The behavioral question: does the market shift more?",
    { x:0.85, y:5.95, w:11.7, h:0.7, fontFace:F.title, fontSize:18, italic:true, bold:true, color:C.NAVY });
});

// ─── 9. BACKTEST ENGINE ──────────────────────────────────────────────────
builders.push(s => {
  header(s, "The backtest engine", "5/5 honesty gates pass on synthetic data");
  s.addText("threshold → ¼-Kelly → settle at vigged odds → block-bootstrap by game",
    { x:0.55, y:1.7, w:12.3, h:0.5, fontFace:F.body, fontSize:18, italic:true, color:C.DEEP, align:"center" });
  const rows = [
    [{ text:"Gate", options:{ bold:true, color:C.CREAM, fill:C.NAVY }},
     { text:"What it proves", options:{ bold:true, color:C.CREAM, fill:C.NAVY }}],
    [{ text:"const-0.5 → Brier 0.25", options:{ color:C.NAVY, bold:true }},
     { text:"metrics wired correctly", options:{ color:C.INK }}],
    [{ text:"always-favorite → loses ≈ the vig", options:{ color:C.NAVY, bold:true }},
     { text:"engine doesn't invent free money", options:{ color:C.INK }}],
    [{ text:"random → loses ≈ the vig", options:{ color:C.NAVY, bold:true }},
     { text:"same — no spurious edge", options:{ color:C.INK }}],
    [{ text:"perfect model on biased market → +14% ROI, p=0.000", options:{ color:C.NAVY, bold:true }},
     { text:"engine CAN detect a real edge", options:{ color:C.ACCENT, bold:true }}],
    [{ text:"market-as-variant → 0 bets", options:{ color:C.NAVY, bold:true }},
     { text:"no fake edge against the market", options:{ color:C.INK }}],
  ];
  s.addTable(rows, { x:0.55, y:2.4, w:12.3, colW:[6.0, 6.3],
    fontFace:F.body, fontSize:15, border:{ type:"solid", color:C.SKY, pt:1 }, rowH:0.6 });
  s.addText("Why bootstrap by game (not tick)?  Within-game ticks share one outcome — effective n is games.",
    { x:0.55, y:6.6, w:12.3, h:0.4, fontFace:F.body, fontSize:13, italic:true, color:C.SKY, align:"center" });
});

// ─── 10. LIVE PILOT (headline #3) ────────────────────────────────────────
builders.push(s => {
  header(s, "Live pilot · SAS @ OKC, 2026-05-26 (FINAL OKC 127–114)", "Headline figure #3 · 73 in-1H ticks · 6 books");
  const rows = [
    [{ text:"Strategy", options:{ bold:true, color:C.CREAM, fill:C.NAVY }},
     { text:"Bets", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }},
     { text:"ROI", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }}],
    [{ text:"Our model @4% edge", options:{ bold:true, color:C.NAVY }},
     { text:"34", options:{ align:"center", color:C.INK }},
     { text:"−40%", options:{ align:"center", color:C.ACCENT, bold:true, fontSize:20 }}],
    [{ text:"Always-favorite", options:{ color:C.INK }},
     { text:"73", options:{ align:"center", color:C.INK }},
     { text:"+34%", options:{ align:"center", color:C.INK }}],
    [{ text:"Always-trailing", options:{ color:C.INK }},
     { text:"73", options:{ align:"center", color:C.INK }},
     { text:"−81%", options:{ align:"center", color:C.INK }}],
    [{ text:"Random", options:{ color:C.INK }},
     { text:"73", options:{ align:"center", color:C.INK }},
     { text:"−31%", options:{ align:"center", color:C.INK }}],
  ];
  s.addTable(rows, { x:0.55, y:1.7, w:6.0, colW:[3.2, 1.0, 1.8],
    fontFace:F.body, fontSize:15, border:{ type:"solid", color:C.SKY, pt:1 }, rowH:0.6 });
  s.addShape("roundRect", { x:6.85, y:1.7, w:6.0, h:5.0,
    fill:{color:C.CREAM}, line:{color:C.TEAL, width:1.5}, rectRadius:0.1 });
  s.addText("The lesson IS the result.",
    { x:7.1, y:1.85, w:5.6, h:0.5, fontFace:F.title, fontSize:20, bold:true, color:C.NAVY });
  s.addText("Model faded SA (underdog) early when the score was close. OKC pulled away and won 127–114.",
    { x:7.1, y:2.45, w:5.6, h:1.2, fontFace:F.body, fontSize:14, color:C.INK });
  s.addText([
    { text:"'Always favorite' looks brilliant — " },
    { text:"only because the favorite happened to win this one game.", options:{ italic:true, color:C.DEEP }},
  ], { x:7.1, y:3.65, w:5.6, h:1.3, fontFace:F.body, fontSize:14, color:C.INK });
  s.addText([
    { text:"This is the " },
    { text:"n=1 problem", options:{ bold:true, color:C.ACCENT }},
    { text:" made tangible — the methodological backbone of the project." },
  ], { x:7.1, y:5.0, w:5.6, h:1.5, fontFace:F.body, fontSize:14, color:C.INK });
});

// ─── 11. LIQUIDITY × SAMPLE SIZE ─────────────────────────────────────────
builders.push(s => {
  header(s, "Liquidity × sample size are everything", "Two backtests, opposite results · same model family");
  const rows = [
    [{ text:"", options:{ fill:C.NAVY }},
     { text:"Liquid sportsbook (live)", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }},
     { text:"Stale Kalshi 1H (archive)", options:{ bold:true, color:C.CREAM, fill:C.NAVY, align:"center" }}],
    [{ text:"Games", options:{ bold:true, color:C.NAVY }},
     { text:"1", options:{ align:"center", color:C.INK, bold:true, fontSize:22 }},
     { text:"4", options:{ align:"center", color:C.INK, bold:true, fontSize:22 }}],
    [{ text:"Model ROI", options:{ bold:true, color:C.NAVY }},
     { text:"−40%", options:{ align:"center", color:C.ACCENT, bold:true, fontSize:24 }},
     { text:"+100%+", options:{ align:"center", color:C.ACCENT, bold:true, fontSize:24 }}],
  ];
  s.addTable(rows, { x:1.5, y:1.7, w:10.3, colW:[3.3, 3.5, 3.5],
    fontFace:F.body, fontSize:16, border:{ type:"solid", color:C.SKY, pt:1 }, rowH:1.0 });
  s.addShape("roundRect", { x:0.55, y:5.1, w:12.3, h:1.75,
    fill:{color:C.CREAM}, line:{color:C.ACCENT, width:1.5}, rectRadius:0.1 });
  s.addText("The +100% against Kalshi is stale mid-prices + n=4 + no slippage — exactly the trap CLAUDE.md warns about.",
    { x:0.85, y:5.25, w:11.7, h:0.7, fontFace:F.body, fontSize:15, color:C.INK });
  s.addText("Real liquid markets are tight. The trustworthy answer needs many liquid-market games.",
    { x:0.85, y:5.95, w:11.7, h:0.7, fontFace:F.title, fontSize:17, italic:true, bold:true, color:C.NAVY });
});

// ─── 12. HALAWI TIE-BACK ─────────────────────────────────────────────────
builders.push(s => {
  header(s, "Connecting back to Halawi", "The Aggregate column — applied to NBA");
  s.addText([
    { text:"Halawi's buried result: ", options:{ bold:true }},
    { text:"4·LM + 1·crowd > either alone — because the errors are " },
    { text:"independent.", options:{ bold:true, italic:true, color:C.ACCENT }},
  ], { x:0.55, y:1.7, w:12.3, h:0.85, fontFace:F.body, fontSize:18, color:C.INK });
  s.addText([
    { text:"Our structural model and the live market are also " },
    { text:"partly independent error sources", options:{ bold:true, color:C.NAVY }},
    { text:" — model reads game state, market absorbs sentiment + inside flow." },
  ], { x:0.55, y:2.65, w:12.3, h:1.2, fontFace:F.body, fontSize:18, color:C.INK });
  s.addShape("roundRect", { x:0.55, y:4.0, w:12.3, h:2.4,
    fill:{color:C.CREAM}, line:{color:C.TEAL, width:1.5}, rectRadius:0.1 });
  s.addText("V3 — Halawi-aggregate variant",
    { x:0.85, y:4.15, w:11.7, h:0.4, fontFace:F.body, fontSize:14, italic:true, color:C.DEEP });
  s.addText("p̂_aggregate  =  w · p_model  +  (1 − w) · p_market_devig",
    { x:0.85, y:4.55, w:11.7, h:0.55, fontFace:F.code, fontSize:20, color:C.NAVY, bold:true });
  s.addText("Weight chosen by validation Brier; the aggregate's Brier ≤ min(component Briers).",
    { x:0.85, y:5.15, w:11.7, h:0.4, fontFace:F.body, fontSize:14, italic:true, color:C.DEEP });
  s.addText("The model's job isn't to BEAT the market everywhere — it's to COMPLEMENT it where the crowd's bias is strongest (H1 / H4).",
    { x:0.85, y:5.6, w:11.7, h:0.8, fontFace:F.body, fontSize:15, color:C.INK });
});

// ─── 13. LIMITATIONS ─────────────────────────────────────────────────────
builders.push(s => {
  header(s, "Limitations & future work", "What we'd do next");
  const items = [
    ["Sample size",       "Powered backtest needs ~1,000 liquid-market games. Two paths: paid the-odds-api historical (~$59, one month) or playoff capture (free, accumulating)."],
    ["Horizon",           "V2 is 1st-half winner; live demo extended to full-game via parallel model (Brier 0.207). Snapshots are 1H-only — 2nd-half coverage requires rebuilding."],
    ["Market reactivity", "Real deployment would face adverse selection + sportsbook limits. Kalshi (peer-to-peer) sidesteps the account-limit issue."],
    ["Variants V1/V3/V4/V6", "Architecturally ready in the shared eval harness; need multi-venue in-play history to fit & evaluate."],
  ];
  let y = 1.7;
  items.forEach(([h, body]) => {
    s.addText(h, { x:0.55, y, w:3.2, h:0.5, fontFace:F.title, fontSize:16, bold:true, color:C.NAVY });
    s.addText(body, { x:3.85, y, w:9.0, h:1.1, fontFace:F.body, fontSize:14, color:C.INK });
    y += 1.2;
  });
});

// ─── 14. TAKEAWAYS ───────────────────────────────────────────────────────
builders.push(s => {
  header(s, "Takeaways", "What we shipped, and what it says");
  const items = [
    ["Calibrated WP model",                          "Brier 0.149 OOS · ECE 0.008 — simple, defensible artifact."],
    ["Pre-registered behavioral test passed",        "Trailing-team overreaction is real on the held-out season (p < 0.0001)."],
    ["Full pipeline runs end-to-end on real data",   "model → de-vig → edge → Kelly → settle → bootstrap. 5/5 honesty gates."],
    ["The honest backtest answer",                   "Pipeline ready · scale gates the trustworthy P&L (n=1 lesson made tangible)."],
    ["Halawi-tied story",                            "Model and crowd are complementary error sources — not competing oracles."],
  ];
  let y = 1.7;
  items.forEach(([h, body], i) => {
    s.addShape("ellipse", { x:0.55, y:y+0.05, w:0.5, h:0.5, fill:{color:C.ACCENT}, line:{color:C.ACCENT,width:0} });
    s.addText(String(i+1), { x:0.55, y:y+0.07, w:0.5, h:0.5,
      fontFace:F.title, fontSize:16, bold:true, color:C.NAVY, align:"center", valign:"middle" });
    s.addText(h, { x:1.25, y, w:12.0, h:0.45, fontFace:F.title, fontSize:17, bold:true, color:C.NAVY });
    s.addText(body, { x:1.25, y:y+0.45, w:12.0, h:0.6, fontFace:F.body, fontSize:14, color:C.INK });
    y += 1.05;
  });
  s.addText("Thank you. Questions?",
    { x:0.55, y:6.95, w:12.3, h:0.45, fontFace:F.title, fontSize:20, italic:true, bold:true, color:C.TEAL, align:"center" });
});

// ─── BUILD ───────────────────────────────────────────────────────────────
builders.forEach((build, i) => {
  const s = pres.addSlide();
  build(s);
  if (i > 0) footer(s, i + 1);
});

pres.writeFile({ fileName: "slides/final_deck.pptx" }).then(name => {
  console.log("Wrote:", name);
});
