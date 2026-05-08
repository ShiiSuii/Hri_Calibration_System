import os
import pandas as pd
import json
import glob
import numpy as np

def export_aggregate_metrics(logs_dir="logs", output_file="aggregate_metrics.csv"):
    """
    Parses all summary JSONs and CSV logs in logs_dir and exports an aggregated CSV.
    """
    summary_files = glob.glob(os.path.join(logs_dir, "*_summary.json"))
    
    all_data = []
    
    for sf in summary_files:
        with open(sf, 'r') as f:
            data = json.load(f)
            
        # Try to find corresponding CSV for ambiguity count
        csv_file = sf.replace("_summary.json", ".csv")
        ambiguity_count = 0
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                if 'ambiguous_case' in df.columns:
                    ambiguity_count = df['ambiguous_case'].sum()
            except Exception as e:
                print(f"Error reading {csv_file}: {e}")
        
        row = {
            "participant_id": data.get("participant_id"),
            "condition": data.get("condition"),
            "scenario": data.get("scenario"),
            "trial_id": data.get("trial_id"),
            "repetition": data.get("repetition_number"),
            "n_transitions": data.get("number_of_state_transitions"),
            "n_attention_losses": data.get("number_of_attention_losses"),
            "n_resumes": data.get("number_of_resumes"),
            "mean_det_latency_ms": data.get("mean_detection_latency_ms"),
            "mean_act_latency_ms": data.get("mean_action_latency_ms"),
            "ambiguous_cases": ambiguity_count,
        }
        all_data.append(row)
        
    if not all_data:
        print("No log files found.")
        return

    agg_df = pd.DataFrame(all_data)
    agg_df.to_csv(output_file, index=False)
    print(f"Aggregated metrics exported to {output_file}")
    
    # Calculate group means
    if 'condition' in agg_df.columns:
        summary = agg_df.groupby(['condition', 'scenario']).mean(numeric_only=True)
        print("\n--- Group Summary (Means) ---")
        print(summary)

if __name__ == "__main__":
    export_aggregate_metrics()
