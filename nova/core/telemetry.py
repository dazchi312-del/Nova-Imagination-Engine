# core/telemetry.py
# Phase 10: Hardware Circuit Breaker via NVML

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

class HardwareBreaker:
    def __init__(self, temp_limit=82, vram_limit_pct=95.0):
        self.temp_limit = temp_limit
        self.vram_limit_pct = vram_limit_pct
        self.active = False
        
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                # Assuming the RTX 5090 is GPU 0
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(0) 
                self.active = True
            except pynvml.NVMLError as e:
                print(f"[Telemetry] NVML Init failed: {e}")

    def check_pressure(self) -> tuple[bool, str]:
        """Returns (Is_Safe: bool, Status_Message: str)"""
        if not self.active:
            return True, "[Telemetry] Offline - Bypassing Breaker"
            
        temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
        mem = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
        vram_pct = (mem.used / mem.total) * 100
        
        status = f"Temp: {temp}C | VRAM: {vram_pct:.1f}%"
        
        # The Circuit Breaker Logic
        if temp >= self.temp_limit or vram_pct >= self.vram_limit_pct:
            return False, f"LIMIT EXCEEDED ({status})"
            
        return True, f"Nominal ({status})"
    # Add to the bottom of core/telemetry.py
if __name__ == "__main__":
    print("[Diagnostic] Initiating Hardware Sensor Test...")
    breaker = HardwareBreaker(temp_limit=80, vram_limit_pct=92.0)
    
    if not breaker.active:
        print("[Diagnostic] FAILED. NVML not active or GPU not found.")
    else:
        is_safe, status = breaker.check_pressure()
        print(f"[Diagnostic] Sensor Active.")
        print(f"[Diagnostic] Status: {status}")
        print(f"[Diagnostic] Circuit Breaker Safe: {is_safe}")