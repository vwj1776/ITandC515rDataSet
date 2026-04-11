import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def get_extension(filename):
    """Extract file type, handling recovery tool mangling."""
    filename = str(filename)
    if '.' in filename:
        return filename.split('.')[-1].lower()
    elif '_' in filename:
        return filename.split('_')[-1].lower()
    return 'unknown'

def generate_master_summary(recovered_csv, sample_csv, output_csv):
    print("\n--- PHASE 1 & 2: Data Ingestion & Summary Generation ---")
    df_recovered = pd.read_csv(recovered_csv)
    df_sample = pd.read_csv(sample_csv)
    
    # Extract file types
    df_sample['File_Type'] = df_sample['Just_The_Filename'].apply(get_extension)
    df_recovered['File_Type'] = df_recovered['File_Name'].apply(get_extension)
    
    # Calculate baseline sample sizes per file type
    sample_totals = df_sample.groupby('File_Type').size().to_dict()
    
    # Identify all valid testing combinations that were physically run
    valid_tests = df_recovered[['Drive', 'Deletion_Method']].drop_duplicates().to_dict('records')
    recovery_methods = df_recovered['Recovery_Method'].unique()
    
    # Create expected combinations to ensure completely failed recoveries (0%) are included
    expected_rows = []
    for test in valid_tests:
        for rm in recovery_methods:
            for ft in sample_totals.keys():
                expected_rows.append({
                    'Drive': test['Drive'],
                    'Deletion_Method': test['Deletion_Method'],
                    'Recovery_Method': rm,
                    'File_Type': ft
                })
    df_expected = pd.DataFrame(expected_rows)

    # Group and count recoveries
    counts = df_recovered.groupby(['Drive', 'Recovery_Method', 'Deletion_Method', 'File_Type']).size().reset_index(name='Total_Recovered')
    
    # Merge expected with actual counts, filling any missing tests with 0 recoveries
    counts = pd.merge(df_expected, counts, on=['Drive', 'Recovery_Method', 'Deletion_Method', 'File_Type'], how='left')
    counts['Total_Recovered'] = counts['Total_Recovered'].fillna(0)
    
    # Calculate true percentages based on exact sample size
    counts['Percentage'] = counts.apply(
        lambda row: round((row['Total_Recovered'] / sample_totals.get(row['File_Type'], 0)) * 100, 2) 
        if sample_totals.get(row['File_Type'], 0) > 0 else None, 
        axis=1
    )
    
    # Drop any leftover artifacts that didn't exist in the sample
    counts = counts.dropna(subset=['Percentage'])
    
    # Sort and save
    counts = counts.sort_values(by=['Drive', 'Recovery_Method', 'Deletion_Method', 'Total_Recovered'], ascending=[True, True, True, False])
    counts.to_csv(output_csv, index=False)
    print(f"Success! Master summary saved to: {output_csv}")
    return counts

def generate_overall_summary(recovered_csv, sample_csv, output_csv):
    print("\n--- PHASE 2B: Overall Summary Generation ---")
    df_recovered = pd.read_csv(recovered_csv)
    df_sample = pd.read_csv(sample_csv)
    
    # Calculate total files in the entire baseline sample
    total_sample_files = len(df_sample['Just_The_Filename'].dropna())
    
    # Identify all valid testing combinations that were physically run
    valid_tests = df_recovered[['Drive', 'Deletion_Method']].drop_duplicates().to_dict('records')
    recovery_methods = df_recovered['Recovery_Method'].unique()
    
    # Create expected combinations for the overall summary
    expected_rows = []
    for test in valid_tests:
        for rm in recovery_methods:
            expected_rows.append({
                'Drive': test['Drive'],
                'Deletion_Method': test['Deletion_Method'],
                'Recovery_Method': rm
            })
    df_expected = pd.DataFrame(expected_rows)

    # Group by Drive, Recovery Method, and Deletion Method
    counts = df_recovered.groupby(['Drive', 'Recovery_Method', 'Deletion_Method']).size().reset_index(name='Total_Recovered')
    
    # Merge expected with actual counts, filling any missing tests with 0 recoveries
    counts = pd.merge(df_expected, counts, on=['Drive', 'Recovery_Method', 'Deletion_Method'], how='left')
    counts['Total_Recovered'] = counts['Total_Recovered'].fillna(0)
    
    counts['Percentage'] = ((counts['Total_Recovered'] / total_sample_files) * 100).round(2)
    
    # Map Drive Type and S/N based on known dataset structure
    counts['Drive Type'] = counts['Drive'].apply(lambda d: 'HDD' if d in ['JZ0', '1B8', 'W9B'] else 'SSD')
    counts['S/N'] = counts.apply(lambda r: f"{r['Drive']} {r['Drive Type']}", axis=1)
    
    # Reorder columns to exactly match your requested format
    counts = counts[['Drive Type', 'S/N', 'Recovery_Method', 'Deletion_Method', 'Total_Recovered', 'Percentage']]
    counts = counts.sort_values(by=['Drive Type', 'S/N', 'Deletion_Method', 'Recovery_Method'])
    
    # Save and display
    counts.to_csv(output_csv, index=False)
    print(f"Success! Overall summary saved to: {output_csv}")
    print("\nPreview:")
    print(f"{'Drive Type':<10}\t{'S/N':<12}\t{'Recovery_Method':<15}\t{'Deletion_Method':<15}\t{'Total_Recovered':<15}\t{'Percentage'}")
    for _, row in counts.iterrows():
        print(f"{row['Drive Type']:<10}\t{row['S/N']:<12}\t{row['Recovery_Method']:<15}\t{row['Deletion_Method']:<15}\t{row['Total_Recovered']:<15}\t{row['Percentage']}")
    return counts

def generate_visualization(df_summary, output_img):
    print("\n--- PHASE 3: Data Visualization ---")
    
    # Create a grouped bar chart split into two columns by Drive Type
    g = sns.catplot(
        data=df_summary, 
        x='Deletion_Method', 
        y='Percentage', 
        hue='Recovery_Method', 
        col='Drive Type', 
        kind='bar',
        height=6, 
        aspect=1.2
    )
    
    g.fig.subplots_adjust(top=0.85) # Make room for the main title
    g.fig.suptitle('Average Recovery Success Rate by Deletion Method and Drive Type')
    g.set_axis_labels('Deletion Method', 'Recovery Percentage (%)')
    
    plt.savefig(output_img)
    print(f"Success! Visualization saved to: {output_img}")
    plt.show() # This makes the graph actually pop up on your screen!

def generate_deep_analytics(df_summary, base_dir):
    print("\n--- PHASE 4: Deep-Dive Analytics ---")
    # Filter out the control baseline so it doesn't skew average success metrics
    df_analytics = df_summary[df_summary['Deletion_Method'] != 'control']
    
    def save_stat(group_col, filename):
        stats = df_analytics.groupby(group_col)['Percentage'].mean().round(2).reset_index()
        stats = stats.sort_values(by='Percentage', ascending=False)
        stats.rename(columns={'Percentage': 'Average_Recovery_Percentage'}, inplace=True)
        
        out_path = os.path.join(base_dir, filename)
        stats.to_csv(out_path, index=False)
        print(f"Saved analytics for {group_col} -> {filename}")

    save_stat('Drive', 'analytics_by_drive.csv')
    save_stat('File_Type', 'analytics_by_file_type.csv')
    save_stat('Recovery_Method', 'analytics_by_recovery_method.csv')
    save_stat('Deletion_Method', 'analytics_by_deletion_method.csv')
    print("All analytics processing complete!")

if __name__ == "__main__":
    # Base Paths
    BASE_DIR = r"c:\Users\vj234\Desktop\codeForDataSet"
    RECOVERED_CSV = os.path.join(BASE_DIR, "exact_matches_cleaned.csv")
    SAMPLE_CSV = os.path.join(BASE_DIR, "filenames_only.csv")
    SUMMARY_CSV = os.path.join(BASE_DIR, "recovery_summary.csv")
    OVERALL_CSV = os.path.join(BASE_DIR, "overall_recovery_summary.csv")
    CHART_IMG = os.path.join(BASE_DIR, "recovery_success_chart.png")
    
    print("==================================================")
    print("      DATA RECOVERY EXPERIMENT PIPELINE V1.0      ")
    print("==================================================")
    master_df = generate_master_summary(RECOVERED_CSV, SAMPLE_CSV, SUMMARY_CSV)
    overall_df = generate_overall_summary(RECOVERED_CSV, SAMPLE_CSV, OVERALL_CSV)
    generate_visualization(overall_df, CHART_IMG)
    generate_deep_analytics(master_df, BASE_DIR)
