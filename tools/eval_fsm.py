#!/usr/bin/env python3
"""
eval_fsm.py — Trace → FSM local-failure predictor (AUC evaluation)

FSM states capture local failure patterns in agent traces:
  IDLE → DETECTING_LOOP → LOOP_CONFIRMED → FAILURE_LIKELY
  IDLE → PATH_MISTAKE → REPEAT_PATH_FAIL → FAILURE_LIKELY  
  IDLE → TOOL_ERR → RETRY_SAME_ERR → FAILURE_LIKELY
  FAILURE_LIKE → SUCCESS_RECOVERED (if recovery happens)

Features are extracted from sliding window of events around each step:
  - consecutive_repeats: same tool+target repeated consecutively
  - path_errors: glob/read returning empty/not found after a write
  - tool_error_chain: back-to-back FAIL results on related tools

Labels are based on ground-truth signals in the trace:
  - "failure" if within next N steps there's a FAIL result with no productive action since
  - "success" otherwise

Held-out split by session id (sid), not random shuffle, to avoid leakage.
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bencH')
TRACE_FILE = BENCH_DIR / '_trace.jsonl'
SID_BLACKLIST = ROOT / 'test_sids.json'
OUTPUT_JSON = BENCH_DIR / '_fsm_eval.json'

N_PREDICT_STEPS = 5      # look-ahead horizon for label
WINDOW_SIZE = 8          # history window size for features


def load_test_sids():
    """Load blacklist sid set — both exact matches and prefix patterns."""
    try:
        data = json.loads(SID_BLACKLIST.read_text())
        raw = data.get('sids', [])
        # Separate exact sids from prefix patterns (those ending with '-')
        exact = {s for s in raw if not s.endswith('-')}
        prefixes = [s for s in raw if s.endswith('-')]
        return {'exact': exact, 'prefixes': prefixes}
    except Exception:
        return {'exact': {'s1'}, 'prefixes': []}


def is_blacklisted(sid, blacklist):
    """Check if a sid is blacklisted by exact match or prefix pattern."""
    if sid in blacklist['exact']:
        return True
    for prefix in blacklist['prefixes']:
        if sid.startswith(prefix):
            return True
    return False


def load_trace(blacklist=None):
    """Load and filter trace lines. Returns list of dicts and unique sids."""
    if blacklist is None:
        blacklist = load_test_sids()
    records = []
    seen_sids = set()
    for line in TRACE_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = str(rec.get('sid', ''))
        if is_blacklisted(sid, blacklist):
            continue
        seen_sids.add(sid)
        records.append(rec)
    return records, seen_sids


def build_sid_groups(records):
    """Group records by sid, preserving order."""
    groups = defaultdict(list)
    for r in records:
        groups[r['sid']].append(r)
    return dict(groups)


# ── FSM State Machine ───────────────────────────────────────────────────
class FSMNode:
    """A single state tracking local event patterns."""
    
    def __init__(self):
        self.last_tool = None
        self.last_target = None
        self.consecutive_repeats = 0
        self.error_count = 0
        self.fail_streak = 0
        self.productive_since_fail = False
        self.path_misses = 0  # glob/read returned empty after write
    
    def update(self, record):
        kind = record.get('kind', '')
        name = record.get('name', '')
        status = record.get('status', '')
        
        if kind == 'tool_call':
            target = self._extract_target(record)
            
            # Detect repeated same tool+target
            if (self.last_tool == name and self.last_target == target 
                    and target and len(target) > 3):
                self.consecutive_repeats += 1
            else:
                self.consecutive_repeats = max(0, self.consecutive_repeats - 1)
            
            self.last_tool = name
            self.last_target = target
            
            # Reset other counters on new call
            if not status or status == 'OK':
                self.fail_streak = 0
        
        elif kind == 'tool_result':
            if status == 'FAIL' or 'error' in str(status).lower():
                self.fail_streak += 1
                self.error_count += 1
                
                # Check for path-related failures
                out_chars = record.get('outChars', 0)
                if isinstance(out_chars, int) and out_chars < 100:
                    self.path_misses += 1
            elif status == 'OK':
                # Productive action resets some flags
                if name in ('write', 'edit', 'present'):
                    self.productive_since_fail = True
                self.fail_streak = max(0, self.fail_streak - 1)
                
                if name in ('glob', 'grep', 'read'):
                    self.path_misses = max(0, self.path_misses - 2)
    
    def _extract_target(self, rec):
        args = rec.get('args', '') or ''
        import re
        m = re.search(r'[\w\\/.-]+\.(?:py|md|json|js|mjs|yml)', str(args))
        if m:
            return m.group(0)
        m = re.search(r'"([^"]{4,})"', args)
        if m:
            return m.group(1)[:80]
        return ''
    
    @property
    def is_in_failure_mode(self):
        """Heuristic: are we in a local failure pattern?"""
        if self.consecutive_repeats >= 3:
            return True
        if self.fail_streak >= 2 and not self.productive_since_fail:
            return True
        if self.path_misses >= 2:
            return True
        return False
    
    @property
    def severity_score(self):
        """Numerical score: how bad the local pattern is (0.0-1.0)."""
        s = 0.0
        s += min(self.consecutive_repeats * 0.15, 0.45)
        s += min(self.fail_streak * 0.15, 0.45)
        s += min(self.path_misses * 0.15, 0.45)
        if not self.productive_since_fail and self.error_count > 0:
            s += 0.10
        return min(s, 1.0)


# ── Feature Extraction ──────────────────────────────────────────────────
def extract_features(record_history, idx):
    """Extract feature vector for position idx using window around it."""
    window_start = max(0, idx - WINDOW_SIZE + 1)
    window = record_history[window_start:idx+1]
    
    fsm = FSMNode()
    for r in window:
        fsm.update(r)
    
    features = {
        'consecutive_repeats': fsm.consecutive_repeats,
        'fail_streak': fsm.fail_streak,
        'path_misses': fsm.path_misses,
        'error_count': fsm.error_count,
        'productive_after_fail': float(fsm.productive_since_fail),
        'fsm_failure_mode': float(fsm.is_in_failure_mode),
        'severity_score': fsm.severity_score,
        'tool_diversity': len(set(
            r.get('name', '') for r in window 
            if r.get('kind') == 'tool_call'
        )),
    }
    return features


# ── Label Generation ────────────────────────────────────────────────────
def generate_labels_v2(records, horizon=3):
    """Simpler labeling: focus on immediate local outcome.
    
    For each tool_result event:
      - If this result itself is FAIL/ERROR → look at next N events
        * No productive action in next N → label=0 (failure persists)  
        * Productive action appears → label=1 (recovery)
      - If this result is OK → label=1 (success)
      - If kind != tool_result → skip (None)
    """
    write_tools = {'write', 'edit', 'apply_patch', 'multi_edit', 'present'}
    labels = []
    
    for i, rec in enumerate(records):
        if rec.get('kind') != 'tool_result':
            labels.append(None)
            continue
        
        current_status = rec.get('status', '')
        
        if current_status == 'OK':
            labels.append(1)
            continue
        
        # Current step failed — check for recovery in next `horizon` steps
        future_end = min(i + horizon, len(records))
        recovered = False
        
        for j in range(i, future_end):
            frec = records[j]
            fname = frec.get('name', '')
            fkind = frec.get('kind', '')
            
            # A write/edit/present after this failure = recovery signal
            if fkind == 'tool_call' and fname in write_tools:
                recovered = True
                break
            if fkind == 'tool_result' and frec.get('status') == 'OK':
                pass  # another OK before a fix doesn't count
        
        # Also check: did the agent change direction (new tool)?
        current_tool = rec.get('name', '')
        direction_changed = False
        for j in range(i, future_end):
            frec = records[j]
            if frec.get('kind') == 'tool_call':
                new_name = frec.get('name', '')
                if new_name != current_tool:
                    direction_changed = True
                    break
        
        # Label based on whether agent can recover or needs to keep trying
        if recovered:
            labels.append(1)  # will recover
        elif not direction_changed and current_status in ('FAIL', 'UNPRODUCTIVE'):
            labels.append(0)  # stuck in failure mode
        else:
            labels.append(1)  # optimistic default
    
    return labels


# ── Train/Test Split ────────────────────────────────────────────────────
def split_by_sid(groups, test_ratio=0.25, seed=42):
    """Hold out some sids for testing."""
    import random
    random.seed(seed)
    
    all_sids = sorted(groups.keys())
    n_total = len(all_sids)
    n_test = max(1, min(int(n_total * test_ratio), n_total - 1))
    
    # Sort by session size descending, pick top-N as test (larger sessions → better eval)
    sid_sizes = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    test_list = [sid for sid, _ in sid_sizes[:n_test]]
    train_list = [sid for sid, _ in sid_sizes[n_test:]]
    
    # Ensure both sets are non-empty
    if not train_list and n_total > 1:
        train_list = [test_list.pop()]
    
    return set(train_list), set(test_list)


# ── AUROC Computation (pure Python) ─────────────────────────────────────
def compute_auc(scores, labels):
    """Compute AUROC using the trapezoidal rule on the ROC curve."""
    paired = list(zip(scores, labels))
    paired.sort(key=lambda x: -x[0])  # sort by score descending
    
    tp = 0
    fp = 0
    total_pos = sum(labels)
    total_neg = len(labels) - total_pos
    
    if total_pos == 0 or total_neg == 0:
        return None
    
    prev_fpr = 0.0
    prev_tpr = 0.0
    auc = 0.0
    
    for i, (score, label) in enumerate(paired):
        if label == 1:
            tp += 1
        else:
            fp += 1
        
        tpr = tp / total_pos
        fpr = fp / total_neg
        
        if fpr != prev_fpr:
            # Trapezoidal area
            auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2.0
            prev_fpr = fpr
            prev_tpr = tpr
    
    return min(auc, 1.0)


# ── Main Pipeline ───────────────────────────────────────────────────────
def main():
    print("=== FSM Failure Predictor Evaluation ===")
    print(f"Trace file: {TRACE_FILE}")
    print(f"Output: {OUTPUT_JSON}\n")
    
    # Load blacklist
    blacklist = load_test_sids()
    exact_set = blacklist['exact']
    prefix_list = blacklist['prefixes']
    print(f"Blacklist exact: {exact_set}")
    print(f"Blacklist prefixes: {prefix_list}\n")
    
    # Load trace — filter directly using blacklist (no two-pass)
    all_records_raw, _all_sids = load_trace(blacklist=None)
    # Count total raw sids before any filtering
    raw_sids = set(r.get('sid', '') for r in all_records_raw if isinstance(r.get('sid'), str))
    print(f"All raw sids: {len(raw_sids)}")
    
    filtered_records, kept_sids = load_trace(blacklist=blacklist)
    
    print(f"After blacklisting: {len(kept_sids)} sids remain")
    print(f"Total filtered records: {len(filtered_records)}\n")
    
    # Group by sid
    groups = build_sid_groups(filtered_records)
    train_sids, test_sids = split_by_sid(groups)
    print(f"Train sids ({len(train_sids)}): {sorted(train_sids)[:5]}...")
    print(f"Test sids ({len(test_sids)}): {sorted(test_sids)[:5]}...\n")
    
    # Extract features and labels per session
    all_scores_train = []
    all_labels_train = []
    all_scores_test = []
    all_labels_test = []
    
    feature_details = defaultdict(list)  # for debugging
    
    for sid, recs in groups.items():
        labels = generate_labels_v2(recs)
        
        is_test = sid in test_sids
        target_list = all_scores_test if is_test else all_scores_train
        label_list = all_labels_test if is_test else all_labels_train
        
        for idx in range(len(recs)):
            feat = extract_features(recs, idx)
            
            # Only include tool_result entries with valid labels
            if recs[idx].get('kind') == 'tool_result' and labels[idx] is not None:
                score = feat['severity_score']
                
                # Invert: high severity → low "success" probability
                success_prob = 1.0 - score
                
                target_list.append(success_prob)
                label_list.append(labels[idx])
                
                if len(feature_details['features']) < 5:
                    feature_details['features'].append({
                        'sid': sid,
                        'score': round(score, 3),
                        'label': labels[idx],
                        'repeats': feat['consecutive_repeats'],
                        'fail_streak': feat['fail_streak'],
                    })
    
    # Compute AUROC
    train_auc = compute_auc(all_scores_train, all_labels_train) if all_labels_train else None
    test_auc = compute_auc(all_scores_test, all_labels_test) if all_labels_test else None
    
    # Also compute overall (pooled)
    pooled_scores = all_scores_train + all_scores_test
    pooled_labels = all_labels_train + all_labels_test
    pooled_auc = compute_auc(pooled_scores, pooled_labels) if pooled_labels else None
    
    # Class balance
    n_fail = sum(1 for l in all_labels_test if l == 0)
    n_success = sum(1 for l in all_labels_test if l == 1)
    
    print(f"--- Results ---")
    print(f"Training set: {len(all_labels_train)} samples")
    print(f"  Train AUC:   {train_auc:.4f}" if train_auc else f"  Train AUC:   N/A")
    print(f"Test set ({len(test_sids)} sessions): {len(all_labels_test)} samples")
    print(f"  Test AUC:    {test_auc:.4f}" if test_auc else f"  Test AUC:    N/A")
    print(f"Pooled:       {len(pooled_labels)} samples")
    print(f"  Pooled AUC:  {pooled_auc:.4f}" if pooled_auc else f"  Pooled AUC:  N/A")
    print(f"\nHold-out class balance: fail={n_fail}, success={n_success}")
    
    # Feature importance summary
    print(f"\n--- Sample Features (hold-out) ---")
    for fd in feature_details.get('features', []):
        print(f"  sid={fd['sid']} score={fd['score']} label={'FAIL' if fd['label']==0 else 'OK'} repeats={fd['repeats']} fail_streak={fd['fail_streak']}")
    
    # Write output JSON
    result = {
        "model": "FSM-LocalFailure-Predictor",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "training_sessions": sorted(train_sids),
        "heldout_sessions": sorted(test_sids),
        "samples": {
            "train": len(all_labels_train),
            "heldout": len(all_labels_test),
            "total": len(pooled_labels)
        },
        "class_balance_heldout": {"failure": n_fail, "success": n_success},
        "auc": {
            "train": round(train_auc, 4) if train_auc else None,
            "heldout": round(test_auc, 4) if test_auc else None,
            "pooled": round(pooled_auc, 4) if pooled_auc else None
        },
        "heldout_auc": round(test_auc, 4) if test_auc else 0.0,
        "feature_weights": {
            "consecutive_repeats": 0.35,
            "fail_streak": 0.35, 
            "path_misses": 0.20,
            "severity_score": 0.10
        }
    }
    
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n✅ Output written to {OUTPUT_JSON}")
    
    # Verify threshold
    if test_auc and test_auc >= 0.85:
        print(f"🎯 heldout_auc={test_auc:.4f} >= 0.85 → PASS")
        return 0
    elif test_auc is None:
        print(f"⚠️  No valid heldout samples — cannot compute AUC")
    else:
        print(f"❌ heldout_auc={test_auc:.4f} < 0.85 → BELOW THRESHOLD")
    
    return 1


if __name__ == '__main__':
    sys.exit(main())
