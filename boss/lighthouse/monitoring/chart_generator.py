"""ChartGenerator component for creating data visualizations.

This module provides functionality for generating charts and graphs
based on monitoring data for visualization in dashboards and reports.
"""

import os
import base64
from io import BytesIO
import logging
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class ChartGenerator:
    """Component for generating data visualization charts.
    
    This class provides methods for creating various types of charts
    and graphs based on monitoring data, which can be included in
    dashboards and reports.
    
    Attributes:
        output_dir: Directory where chart images are saved
        logger: Logger instance for the component
    """
    
    def __init__(self, output_dir: str):
        """Initialize the ChartGenerator.
        
        Args:
            output_dir: Directory where chart images will be saved
        """
        self.logger = logging.getLogger("boss.lighthouse.monitoring.chart_generator")
        
        # Ensure the output directory exists
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up default styling
        plt.style.use('seaborn-v0_8-darkgrid')
        
    def generate_line_chart(
        self,
        data: List[Dict[str, Any]],
        x_key: str,
        y_key: str,
        title: str,
        x_label: str = "",
        y_label: str = "",
        color: str = "blue",
        parse_dates: bool = True,
        as_base64: bool = False
    ) -> Union[str, bytes]:
        """Generate a line chart from the provided data.
        
        Args:
            data: List of data points
            x_key: Key for X-axis values in data dictionaries
            y_key: Key for Y-axis values in data dictionaries
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label
            color: Line color
            parse_dates: Whether to parse X values as dates
            as_base64: Whether to return the chart as base64-encoded string
            
        Returns:
            Path to the generated chart file or base64-encoded image
        """
        try:
            # Extract data for plotting
            x_values = [item.get(x_key) for item in data]
            y_values = [item.get(y_key, 0) for item in data]
            
            # Parse dates if requested
            if parse_dates:
                x_values = [datetime.fromisoformat(x) if isinstance(x, str) else x for x in x_values]
            
            # Create the figure and plot
            plt.figure(figsize=(10, 6))
            plt.plot(x_values, y_values, color=color, marker='o', linestyle='-', linewidth=2)
            
            # Add title and labels
            plt.title(title, fontsize=16)
            plt.xlabel(x_label, fontsize=12)
            plt.ylabel(y_label, fontsize=12)
            
            # Format the x-axis if using dates
            if parse_dates:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
                plt.gcf().autofmt_xdate()
                
            # Add grid
            plt.grid(True, linestyle='--', alpha=0.7)
            
            # Tight layout
            plt.tight_layout()
            
            if as_base64:
                # Save to BytesIO and convert to base64
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=100)
                plt.close()
                buf.seek(0)
                img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
                return f"data:image/png;base64,{img_data}"
            else:
                # Save to file and return the path
                filename = f"{title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                file_path = os.path.join(self.output_dir, filename)
                plt.savefig(file_path, dpi=100)
                plt.close()
                return file_path
        except Exception as e:
            self.logger.error(f"Error generating line chart: {e}")
            # Return empty base64 image or placeholder path
            if as_base64:
                return "data:image/png;base64,"
            else:
                return ""
                
    def generate_bar_chart(
        self,
        data: List[Dict[str, Any]],
        category_key: str,
        value_key: str,
        title: str,
        x_label: str = "",
        y_label: str = "",
        color: str = "blue",
        as_base64: bool = False
    ) -> Union[str, bytes]:
        """Generate a bar chart from the provided data.
        
        Args:
            data: List of data points
            category_key: Key for category values in data dictionaries
            value_key: Key for value values in data dictionaries
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label
            color: Bar color
            as_base64: Whether to return the chart as base64-encoded string
            
        Returns:
            Path to the generated chart file or base64-encoded image
        """
        try:
            # Extract data for plotting
            categories = [str(item.get(category_key, "")) for item in data]
            values = [item.get(value_key, 0) for item in data]
            
            # Create the figure and plot
            plt.figure(figsize=(10, 6))
            plt.bar(categories, values, color=color, alpha=0.7)
            
            # Add title and labels
            plt.title(title, fontsize=16)
            plt.xlabel(x_label, fontsize=12)
            plt.ylabel(y_label, fontsize=12)
            
            # Rotate x-axis labels if needed
            if len(max(categories, key=len)) > 8:
                plt.xticks(rotation=45, ha='right')
                
            # Add grid
            plt.grid(True, axis='y', linestyle='--', alpha=0.7)
            
            # Tight layout
            plt.tight_layout()
            
            if as_base64:
                # Save to BytesIO and convert to base64
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=100)
                plt.close()
                buf.seek(0)
                img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
                return f"data:image/png;base64,{img_data}"
            else:
                # Save to file and return the path
                filename = f"{title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                file_path = os.path.join(self.output_dir, filename)
                plt.savefig(file_path, dpi=100)
                plt.close()
                return file_path
        except Exception as e:
            self.logger.error(f"Error generating bar chart: {e}")
            # Return empty base64 image or placeholder path
            if as_base64:
                return "data:image/png;base64,"
            else:
                return ""
                
    def generate_pie_chart(
        self,
        data: List[Dict[str, Any]],
        label_key: str,
        value_key: str,
        title: str,
        as_base64: bool = False
    ) -> Union[str, bytes]:
        """Generate a pie chart from the provided data.
        
        Args:
            data: List of data points
            label_key: Key for label values in data dictionaries
            value_key: Key for value values in data dictionaries
            title: Chart title
            as_base64: Whether to return the chart as base64-encoded string
            
        Returns:
            Path to the generated chart file or base64-encoded image
        """
        try:
            # Extract data for plotting
            labels = [str(item.get(label_key, "")) for item in data]
            values = [item.get(value_key, 0) for item in data]
            
            # Create the figure and plot
            plt.figure(figsize=(8, 8))
            plt.pie(values, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
            
            # Add title
            plt.title(title, fontsize=16)
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            plt.axis('equal')
            
            # Tight layout
            plt.tight_layout()
            
            if as_base64:
                # Save to BytesIO and convert to base64
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=100)
                plt.close()
                buf.seek(0)
                img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
                return f"data:image/png;base64,{img_data}"
            else:
                # Save to file and return the path
                filename = f"{title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                file_path = os.path.join(self.output_dir, filename)
                plt.savefig(file_path, dpi=100)
                plt.close()
                return file_path
        except Exception as e:
            self.logger.error(f"Error generating pie chart: {e}")
            # Return empty base64 image or placeholder path
            if as_base64:
                return "data:image/png;base64,"
            else:
                return ""
                
    def generate_multi_line_chart(
        self,
        data_series: List[Tuple[List[Dict[str, Any]], str, str]],
        x_key: str,
        title: str,
        x_label: str = "",
        y_label: str = "",
        parse_dates: bool = True,
        as_base64: bool = False
    ) -> Union[str, bytes]:
        """Generate a multi-line chart from the provided data series.
        
        Args:
            data_series: List of (data, y_key, label) tuples
            x_key: Key for X-axis values in data dictionaries
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label
            parse_dates: Whether to parse X values as dates
            as_base64: Whether to return the chart as base64-encoded string
            
        Returns:
            Path to the generated chart file or base64-encoded image
        """
        try:
            # Create the figure
            plt.figure(figsize=(10, 6))
            
            # Plot each data series
            for data, y_key, label in data_series:
                # Extract data for plotting
                x_values = [item.get(x_key) for item in data]
                y_values = [item.get(y_key, 0) for item in data]
                
                # Parse dates if requested
                if parse_dates:
                    x_values = [datetime.fromisoformat(x) if isinstance(x, str) else x for x in x_values]
                
                # Plot the line
                plt.plot(x_values, y_values, marker='o', linestyle='-', linewidth=2, label=label)
            
            # Add title and labels
            plt.title(title, fontsize=16)
            plt.xlabel(x_label, fontsize=12)
            plt.ylabel(y_label, fontsize=12)
            
            # Format the x-axis if using dates
            if parse_dates:
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
                plt.gcf().autofmt_xdate()
                
            # Add legend
            plt.legend()
            
            # Add grid
            plt.grid(True, linestyle='--', alpha=0.7)
            
            # Tight layout
            plt.tight_layout()
            
            if as_base64:
                # Save to BytesIO and convert to base64
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=100)
                plt.close()
                buf.seek(0)
                img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
                return f"data:image/png;base64,{img_data}"
            else:
                # Save to file and return the path
                filename = f"{title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                file_path = os.path.join(self.output_dir, filename)
                plt.savefig(file_path, dpi=100)
                plt.close()
                return file_path
        except Exception as e:
            self.logger.error(f"Error generating multi-line chart: {e}")
            # Return empty base64 image or placeholder path
            if as_base64:
                return "data:image/png;base64,"
            else:
                return "" 