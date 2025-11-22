import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Read the CSV files - try different separators
checkouts = pd.read_csv(r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Codes\Input Files\Emirates Checkouts.csv")
trains = pd.read_csv(r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Codes\Input Files\Train_Times.csv")

# Convert to datetime
checkouts['datetime'] = pd.to_datetime('2025-10-31 ' + checkouts['txn_time'])
trains['datetime'] = pd.to_datetime('2025-10-31 ' + trains['arrival_time'])

# CHANGE THESE TIMES TO YOUR DESIRED RANGE
START_HOUR = 8  # Change this
END_HOUR = 9    # Change this

start_time = pd.to_datetime(f'2025-10-31 {START_HOUR:02d}:00:00')
end_time = pd.to_datetime(f'2025-10-31 {END_HOUR:02d}:00:00')
checkouts = checkouts[(checkouts['datetime'] >= start_time) & (checkouts['datetime'] < end_time)].copy()
trains = trains[(trains['datetime'] >= start_time) & (trains['datetime'] < end_time)].copy()

checkouts = checkouts.sort_values('datetime').reset_index(drop=True)
trains = trains.sort_values('datetime').reset_index(drop=True)

# Cluster checkouts within 30 seconds
TIME_THRESHOLD = 20  # seconds

def cluster_checkouts(df, threshold_seconds):
    """Group checkouts that occur within threshold_seconds of each other"""
    clusters = []
    current_cluster = []
    cluster_id = 0
    
    for idx, row in df.iterrows():
        if len(current_cluster) == 0:
            current_cluster.append(idx)
        else:
            last_idx = current_cluster[-1]
            time_diff = (row['datetime'] - df.loc[last_idx, 'datetime']).total_seconds()
            
            if time_diff <= threshold_seconds:
                current_cluster.append(idx)
            else:
                clusters.append({
                    'cluster_id': cluster_id,
                    'start_datetime': df.loc[current_cluster[0], 'datetime'],
                    'end_datetime': df.loc[current_cluster[-1], 'datetime'],
                    'cluster_size': len(current_cluster),
                    'start_time': df.loc[current_cluster[0], 'txn_time']
                })
                cluster_id += 1
                current_cluster = [idx]
    
    if current_cluster:
        clusters.append({
            'cluster_id': cluster_id,
            'start_datetime': df.loc[current_cluster[0], 'datetime'],
            'end_datetime': df.loc[current_cluster[-1], 'datetime'],
            'cluster_size': len(current_cluster),
            'start_time': df.loc[current_cluster[0], 'txn_time']
        })
    
    return clusters

clusters = cluster_checkouts(checkouts, TIME_THRESHOLD)
clusters_df = pd.DataFrame(clusters)

# Create the visualization
fig, ax = plt.subplots(figsize=(18, 10))

# Convert times to seconds since start_time for easier plotting
def to_seconds_since_start(dt):
    return (dt - start_time).total_seconds()

# Plot horizontal bars for checkout clusters
y_position = 0
bar_height = 0.8
colors = plt.cm.viridis(clusters_df['cluster_size'] / clusters_df['cluster_size'].max())

for idx, cluster in clusters_df.iterrows():
    start_sec = to_seconds_since_start(cluster['start_datetime'])
    end_sec = to_seconds_since_start(cluster['end_datetime'])
    duration = end_sec - start_sec
    
    # Make sure we can see even single-checkout clusters
    if duration < 1:
        duration = 2
    
    # Draw the bar
    bar = ax.barh(y_position, duration, left=start_sec, height=bar_height, 
                   color=colors[idx], edgecolor='black', linewidth=1, alpha=0.8)
    
    # Add text showing cluster size
    ax.text(start_sec + duration/2, y_position, f'{cluster["cluster_size"]}', 
            ha='center', va='center', fontweight='bold', fontsize=9, color='white')
    
    y_position += 1

# Plot vertical lines for train arrivals with different colors by stop_id
for idx, train in trains.iterrows():
    train_sec = to_seconds_since_start(train['datetime'])
    
    # Set color based on stop_id
    if train['stop_id'] == 12901:
        color = 'red'
        label = '12901'
    elif train['stop_id'] == 12902:
        color = 'blue'
        label = '12902'
    else:
        color = 'orange'
        label = str(train['stop_id'])
    
    ax.axvline(x=train_sec, color=color, linestyle='--', linewidth=2, alpha=0.7, zorder=10)
    
    # Add train arrival time label at the top
    ax.text(train_sec, len(clusters_df) + 0.5, train['arrival_time'], 
            rotation=45, ha='left', va='bottom', fontsize=8, color=color, fontweight='bold')

# Formatting
ax.set_xlabel('Time (seconds since start)', fontsize=14, fontweight='bold')
ax.set_ylabel('Checkout Cluster #', fontsize=14, fontweight='bold')
ax.set_title(f'Checkout Clusters (Horizontal Bars) vs Train Arrivals (Red Vertical Lines)\n{START_HOUR:02d}:00 - {END_HOUR:02d}:00', 
             fontsize=16, fontweight='bold', pad=20)

# Set x-axis limits and ticks
ax.set_xlim(-5, 3605)  # -5 to 3605 seconds (slightly beyond 1 hour)
ax.set_ylim(-1, len(clusters_df) + 2)

# Add time labels on x-axis (every 5 minutes) - dynamically based on START_HOUR
tick_positions = range(0, 3601, 300)  # Every 5 minutes
tick_labels = [f"{START_HOUR}:{str(int(s//60)).zfill(2)}" for s in tick_positions]
ax.set_xticks(tick_positions)
ax.set_xticklabels(tick_labels, fontsize=10)

# Add grid
ax.grid(True, axis='x', alpha=0.3, linestyle=':', linewidth=1)
ax.set_axisbelow(True)

# # Add legend
# from matplotlib.patches import Patch, Rectangle
# from matplotlib.lines import Line2D
# legend_elements = [
#     Rectangle((0, 0), 1, 1, facecolor='steelblue', edgecolor='black', label='Checkout Cluster (width = duration)'),
#     Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Train Arrival (Stop 12901)'),
#     Line2D([0], [0], color='blue', linestyle='--', linewidth=2, label='Train Arrival (Stop 12902)'),
#     Patch(facecolor='none', edgecolor='none', label='Numbers = People in cluster')
# ]
# ax.legend(handles=legend_elements, loc='upper right', fontsize=11, framealpha=0.9)

# Add colorbar for cluster size
sm = plt.cm.ScalarMappable(cmap='viridis', 
                            norm=plt.Normalize(vmin=clusters_df['cluster_size'].min(), 
                                             vmax=clusters_df['cluster_size'].max()))
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax, pad=0.02)
cbar.set_label('Cluster Size (Number of People)', fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('timeline_clusters_vs_trains.png', dpi=300, bbox_inches='tight')
plt.show()

# Save clusters to CSV
clusters_export = clusters_df.copy()
clusters_export['start_time_str'] = clusters_export['start_datetime'].dt.strftime('%H:%M:%S')
clusters_export['end_time_str'] = clusters_export['end_datetime'].dt.strftime('%H:%M:%S')
clusters_export['duration_seconds'] = (clusters_export['end_datetime'] - clusters_export['start_datetime']).dt.total_seconds()

clusters_export[['cluster_id', 'start_time_str', 'end_time_str', 'cluster_size', 'duration_seconds']].to_csv(
    'timeline_clusters.csv', index=False)

# Print summary
print("="*80)
print("TIMELINE VISUALIZATION SUMMARY")
print("="*80)
print(f"Time period: {checkouts['txn_time'].min()} - {checkouts['txn_time'].max()}")
print(f"Total checkout clusters: {len(clusters_df)}")
print(f"Total train arrivals: {len(trains)}")
print(f"Total checkouts: {len(checkouts)}")
print(f"\nClusters with 10+ people:")
large_clusters = clusters_df[clusters_df['cluster_size'] >= 10]
for _, cluster in large_clusters.iterrows():
    print(f"  Cluster #{cluster['cluster_id']:2d}: {cluster['start_time']} - {cluster['cluster_size']:2d} people")
print("="*80)
print("\nFiles saved:")
print("  - timeline_clusters_vs_trains.png (visualization)")
print("  - timeline_clusters.csv (cluster details)")
print("="*80)