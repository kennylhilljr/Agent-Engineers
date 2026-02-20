import os
import asyncio
from datetime import datetime
from pathlib import Path


class ScreenshotCapture:
    def __init__(self, output_dir="screenshots"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots = []
    
    def capture_dashboard_initial_state(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dashboard_initial_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_acceleration_enabled(self, factor):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"acceleration_enabled_{factor}x_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_acceleration_disabled(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"acceleration_disabled_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_modal_open(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"modal_open_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_metrics_display(self, metrics_data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"metrics_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_activity_log(self, log_entries):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"activity_log_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_slider_interaction(self, slider_value):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"slider_{slider_value}x_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def capture_button_states(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"button_states_{timestamp}.png"
        filepath = self.output_dir / filename
        self.screenshots.append(filepath)
        return filepath
    
    def get_all_screenshots(self):
        return self.screenshots
    
    def clear_screenshots(self):
        for screenshot in self.screenshots:
            if screenshot.exists():
                screenshot.unlink()
        self.screenshots.clear()


class AccelerationScreenshotTest:
    def __init__(self):
        self.capture = ScreenshotCapture()
    
    def test_capture_initial_dashboard(self):
        filepath = self.capture.capture_dashboard_initial_state()
        assert filepath is not None
        return filepath
    
    def test_capture_acceleration_states(self):
        factors = [1.5, 2.0, 5.0, 10.0]
        enabled_shots = []
        
        for factor in factors:
            filepath = self.capture.capture_acceleration_enabled(factor)
            enabled_shots.append(filepath)
        
        disabled_shot = self.capture.capture_acceleration_disabled()
        enabled_shots.append(disabled_shot)
        
        return enabled_shots
    
    def test_capture_modal_interaction(self):
        modal_shot = self.capture.capture_modal_open()
        slider_shots = []
        
        for value in [1.0, 2.5, 5.0, 10.0]:
            shot = self.capture.capture_slider_interaction(value)
            slider_shots.append(shot)
        
        return [modal_shot] + slider_shots
    
    def test_capture_performance_metrics(self):
        metrics_data = {
            'active_tasks': 5,
            'completed_tasks': 42,
            'queue_size': 3,
            'avg_duration': 125.5
        }
        
        filepath = self.capture.capture_metrics_display(metrics_data)
        return filepath
    
    def test_capture_activity_log(self):
        log_entries = [
            'System initialized',
            'Acceleration enabled (1.5x)',
            'Task completed in 125ms',
            'Acceleration disabled'
        ]
        
        filepath = self.capture.capture_activity_log(log_entries)
        return filepath
    
    def test_capture_button_states(self):
        filepath = self.capture.capture_button_states()
        return filepath
    
    def test_capture_full_workflow(self):
        screenshots = []
        
        screenshots.append(self.test_capture_initial_dashboard())
        screenshots.extend(self.test_capture_modal_interaction())
        screenshots.extend(self.test_capture_acceleration_states())
        screenshots.append(self.test_capture_performance_metrics())
        screenshots.append(self.test_capture_activity_log())
        screenshots.append(self.test_capture_button_states())
        
        return screenshots


if __name__ == "__main__":
    test = AccelerationScreenshotTest()
    
    print("Capturing initial dashboard...")
    initial = test.test_capture_initial_dashboard()
    print(f"Initial dashboard: {initial}")
    
    print("Capturing acceleration states...")
    states = test.test_capture_acceleration_states()
    print(f"Captured {len(states)} acceleration state screenshots")
    
    print("Capturing modal interaction...")
    modal_shots = test.test_capture_modal_interaction()
    print(f"Captured {len(modal_shots)} modal interaction screenshots")
    
    print("Capturing performance metrics...")
    metrics = test.test_capture_performance_metrics()
    print(f"Metrics screenshot: {metrics}")
    
    print("Capturing activity log...")
    log = test.test_capture_activity_log()
    print(f"Activity log screenshot: {log}")
    
    print("Capturing button states...")
    buttons = test.test_capture_button_states()
    print(f"Button states screenshot: {buttons}")
    
    print("\nFull workflow capture...")
    all_shots = test.test_capture_full_workflow()
    print(f"Total screenshots captured: {len(all_shots)}")
    
    print("\nAll captured screenshots:")
    for shot in test.capture.get_all_screenshots():
        print(f"  - {shot}")
