#!/usr/bin/env python3
"""
Waste Management Analysis Script
Analyzes waste processing data with daily and cumulative summaries
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple
import argparse
import sys

class WasteAnalyzer:
    """
    A class to analyze waste management data with daily and cumulative reporting
    """
    
    def __init__(self, csv_file: str):
        """
        Initialize the analyzer with CSV data
        
        Args:
            csv_file (str): Path to the CSV file
        """
        self.csv_file = csv_file
        self.data = None
        self.filtered_data = None
        self.daily_summary = {}
        self.cumulative_summary = {}
        
    def load_data(self) -> bool:
        """
        Load and validate CSV data
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.data = pd.read_csv(self.csv_file)
            
            # Clean column names (remove extra spaces and empty columns)
            self.data.columns = self.data.columns.str.strip()
            self.data = self.data.loc[:, ~self.data.columns.str.contains('^Unnamed')]
            
            print(f"✅ Loaded {len(self.data)} records from {self.csv_file}")
            print(f"📊 Columns: {list(self.data.columns)}")
            
            # Validate required columns
            required_cols = ['date', 'material', 'net_weight']
            missing_cols = [col for col in required_cols if col not in self.data.columns]
            
            if missing_cols:
                print(f"❌ Missing required columns: {missing_cols}")
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def filter_data_by_date(self, cutoff_date: str) -> bool:
        """
        Filter data until the specified cutoff date
        
        Args:
            cutoff_date (str): Date in 'YYYY-MM-DD' format
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert date column to datetime
            self.data['date'] = pd.to_datetime(self.data['date'])
            cutoff = pd.to_datetime(cutoff_date)
            
            # Filter data
            self.filtered_data = self.data[
                (self.data['date'] <= cutoff) & 
                (self.data['net_weight'].notna()) & 
                (self.data['net_weight'] > 0)
            ].copy()
            
            date_range = f"{self.filtered_data['date'].min().strftime('%Y-%m-%d')} to {self.filtered_data['date'].max().strftime('%Y-%m-%d')}"
            
            print(f"📅 Filtered data: {len(self.filtered_data)} records")
            print(f"📅 Date range: {date_range}")
            print(f"🏭 Material types: {sorted(self.filtered_data['material'].unique())}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error filtering data: {e}")
            return False
    
    def kg_to_mt(self, kg_value: float) -> float:
        """Convert kilograms to metric tons"""
        return kg_value / 1000
    
    def calculate_daily_summary(self) -> None:
        """Calculate daily material summaries"""
        
        # Group by date and material
        daily_groups = self.filtered_data.groupby(['date', 'material'])['net_weight'].agg(['sum', 'count']).reset_index()
        daily_groups.columns = ['date', 'material', 'total_weight_kg', 'records']
        
        # Calculate daily totals
        daily_totals = daily_groups.groupby('date')['total_weight_kg'].sum().reset_index()
        daily_totals.columns = ['date', 'day_total_kg']
        
        # Merge to get percentages
        daily_with_totals = daily_groups.merge(daily_totals, on='date')
        daily_with_totals['percentage'] = (daily_with_totals['total_weight_kg'] / daily_with_totals['day_total_kg']) * 100
        daily_with_totals['total_weight_mt'] = daily_with_totals['total_weight_kg'].apply(self.kg_to_mt)
        
        # Create daily summary structure
        for _, row in daily_with_totals.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            
            if date_str not in self.daily_summary:
                self.daily_summary[date_str] = {
                    'materials': {},
                    'total_weight_kg': row['day_total_kg'],
                    'total_weight_mt': self.kg_to_mt(row['day_total_kg']),
                    'total_records': 0
                }
            
            self.daily_summary[date_str]['materials'][row['material']] = {
                'total_weight_kg': row['total_weight_kg'],
                'total_weight_mt': row['total_weight_mt'],
                'percentage': row['percentage'],
                'records': row['records']
            }
        
        # Calculate total records per day
        daily_record_counts = self.filtered_data.groupby('date').size()
        for date_str in self.daily_summary:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            if date_obj in daily_record_counts.index:
                self.daily_summary[date_str]['total_records'] = daily_record_counts[date_obj]
    
    def calculate_cumulative_summary(self) -> None:
        """Calculate cumulative material summaries"""
        
        # Group by material for cumulative analysis
        cumulative_groups = self.filtered_data.groupby('material')['net_weight'].agg(['sum', 'count']).reset_index()
        cumulative_groups.columns = ['material', 'total_weight_kg', 'records']
        
        # Calculate total weight for percentages
        grand_total_kg = cumulative_groups['total_weight_kg'].sum()
        
        # Calculate percentages and convert to MT
        cumulative_groups['percentage'] = (cumulative_groups['total_weight_kg'] / grand_total_kg) * 100
        cumulative_groups['total_weight_mt'] = cumulative_groups['total_weight_kg'].apply(self.kg_to_mt)
        
        # Create cumulative summary structure
        for _, row in cumulative_groups.iterrows():
            self.cumulative_summary[row['material']] = {
                'total_weight_kg': row['total_weight_kg'],
                'total_weight_mt': row['total_weight_mt'],
                'percentage': row['percentage'],
                'records': row['records']
            }
        
        self.cumulative_summary['_totals'] = {
            'total_weight_kg': grand_total_kg,
            'total_weight_mt': self.kg_to_mt(grand_total_kg),
            'total_records': len(self.filtered_data),
            'total_days': len(self.daily_summary)
        }
    
    def print_cumulative_report(self) -> None:
        """Print cumulative summary report"""
        totals = self.cumulative_summary['_totals']
        
        print("\n" + "="*60)
        print("CUMULATIVE SUMMARY REPORT")
        print("="*60)
        print(f"Total Weight Processed: {totals['total_weight_mt']:.2f} MT")
        print(f"Total Records: {totals['total_records']:,}")
        print(f"Total Days: {totals['total_days']}")
        print(f"Average Daily Processing: {totals['total_weight_mt']/totals['total_days']:.2f} MT/day")
        
        print(f"\n{'Material Type':<15} {'Weight (MT)':<12} {'Percentage':<12} {'Records':<10}")
        print("-" * 50)
        
        # Sort materials by weight (descending)
        materials = [(k, v) for k, v in self.cumulative_summary.items() if k != '_totals']
        materials.sort(key=lambda x: x[1]['total_weight_mt'], reverse=True)
        
        for material, data in materials:
            print(f"{material:<15} {data['total_weight_mt']:>10.2f} {data['percentage']:>10.1f}% {data['records']:>8}")
    
    def print_daily_report(self, show_all_days: bool = False) -> None:
        """
        Print daily summary report
        
        Args:
            show_all_days (bool): If True, show all days. If False, show sample days.
        """
        print("\n" + "="*80)
        print("DAILY SUMMARY REPORT")
        print("="*80)
        
        sorted_dates = sorted(self.daily_summary.keys())
        
        if show_all_days:
            dates_to_show = sorted_dates
        else:
            # Show first, middle, and last few days
            if len(sorted_dates) <= 6:
                dates_to_show = sorted_dates
            else:
                dates_to_show = [
                    sorted_dates[0],  # First day
                    sorted_dates[1],  # Second day
                    sorted_dates[len(sorted_dates)//2],  # Middle day
                    sorted_dates[-3],  # Third last
                    sorted_dates[-2],  # Second last
                    sorted_dates[-1]   # Last day
                ]
        
        for date in dates_to_show:
            day_data = self.daily_summary[date]
            print(f"\n📅 {date} - Total: {day_data['total_weight_mt']:.2f} MT ({day_data['total_records']} records)")
            
            # Sort materials by weight for this day
            materials = sorted(day_data['materials'].items(), 
                             key=lambda x: x[1]['total_weight_mt'], reverse=True)
            
            for material, mat_data in materials:
                print(f"   {material:<12} | {mat_data['total_weight_mt']:>8.2f} MT | {mat_data['percentage']:>5.1f}% | {mat_data['records']:>3} records")
        
        if not show_all_days and len(sorted_dates) > 6:
            print(f"\n... ({len(sorted_dates) - 6} more days) ...")
            print("Use --show-all-days flag to see complete daily breakdown")
    
    def export_to_csv(self, output_prefix: str = "waste_analysis") -> None:
        """
        Export analysis results to CSV files
        
        Args:
            output_prefix (str): Prefix for output files
        """
        try:
            # Export daily summary
            daily_rows = []
            for date, day_data in self.daily_summary.items():
                for material, mat_data in day_data['materials'].items():
                    daily_rows.append({
                        'date': date,
                        'material': material,
                        'weight_mt': mat_data['total_weight_mt'],
                        'percentage': mat_data['percentage'],
                        'records': mat_data['records'],
                        'day_total_mt': day_data['total_weight_mt']
                    })
            
            daily_df = pd.DataFrame(daily_rows)
            daily_file = f"{output_prefix}_daily.csv"
            daily_df.to_csv(daily_file, index=False)
            print(f"📄 Daily summary exported to: {daily_file}")
            
            # Export cumulative summary
            cumulative_rows = []
            for material, data in self.cumulative_summary.items():
                if material != '_totals':
                    cumulative_rows.append({
                        'material': material,
                        'weight_mt': data['total_weight_mt'],
                        'percentage': data['percentage'],
                        'records': data['records']
                    })
            
            cumulative_df = pd.DataFrame(cumulative_rows)
            cumulative_file = f"{output_prefix}_cumulative.csv"
            cumulative_df.to_csv(cumulative_file, index=False)
            print(f"📄 Cumulative summary exported to: {cumulative_file}")
            
        except Exception as e:
            print(f"❌ Error exporting to CSV: {e}")
    
    def run_analysis(self, cutoff_date: str, show_all_days: bool = False, export: bool = False) -> bool:
        """
        Run complete analysis
        
        Args:
            cutoff_date (str): Cutoff date in 'YYYY-MM-DD' format
            show_all_days (bool): Show all days in daily report
            export (bool): Export results to CSV
            
        Returns:
            bool: True if successful, False otherwise
        """
        print("🔍 Starting Waste Management Analysis...")
        
        # Load and filter data
        if not self.load_data():
            return False
        
        if not self.filter_data_by_date(cutoff_date):
            return False
        
        # Perform analysis
        print("📊 Calculating daily summaries...")
        self.calculate_daily_summary()
        
        print("📊 Calculating cumulative summaries...")
        self.calculate_cumulative_summary()
        
        # Generate reports
        self.print_cumulative_report()
        self.print_daily_report(show_all_days)
        
        # Export if requested
        if export:
            self.export_to_csv()
        
        print("\n✅ Analysis completed successfully!")
        return True

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Analyze waste management data')
    parser.add_argument('csv_file', help='Path to the CSV file')
    parser.add_argument('--cutoff-date', required=True, help='Cutoff date (YYYY-MM-DD)')
    parser.add_argument('--show-all-days', action='store_true', help='Show all days in daily report')
    parser.add_argument('--export', action='store_true', help='Export results to CSV files')
    
    args = parser.parse_args()
    
    # Validate cutoff date format
    try:
        datetime.strptime(args.cutoff_date, '%Y-%m-%d')
    except ValueError:
        print("❌ Error: cutoff-date must be in YYYY-MM-DD format")
        sys.exit(1)
    
    # Run analysis
    analyzer = WasteAnalyzer(args.csv_file)
    success = analyzer.run_analysis(
        cutoff_date=args.cutoff_date,
        show_all_days=args.show_all_days,
        export=args.export
    )
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

# Example usage:
"""
# Basic analysis
python waste_analysis.py betham2.csv.csv --cutoff-date 2025-07-04

# Show all days
python waste_analysis.py betham2.csv.csv --cutoff-date 2025-07-04 --show-all-days

# Export results to CSV
python waste_analysis.py betham2.csv.csv --cutoff-date 2025-07-04 --export

# Full analysis with all options
python waste_analysis.py betham2.csv.csv --cutoff-date 2025-07-04 --show-all-days --export
"""