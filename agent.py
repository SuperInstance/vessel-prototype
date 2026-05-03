#!/usr/bin/env python3
"""
vessel-prototype — Agent/Vessel Separation Architecture for Cocapn Fleet

An Agent is the soul (behavior, goals, memory).
A Vessel is the body (hardware, OS, runtime, sensors).

This prototype demonstrates the separation pattern that allows:
- Agents to migrate between vessels
- Multiple agents per vessel
- Graceful degradation when vessel capabilities change
- Fleet-wide agent scheduling

Built for PurplePincher — the first vessel to host a separated agent.
"""

import json, time, hashlib, os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

@dataclass
class Capability:
    """Something a vessel can do."""
    name: str
    available: bool = True
    priority: int = 0  # Higher = more important
    metadata: Dict = field(default_factory=dict)

@dataclass
class AgentSoul:
    """The portable part of an agent."""
    name: str
    goals: List[str]
    memory_path: str  # Where to load/save memory
    required_caps: List[str]  # Capabilities this agent needs
    preferred_caps: List[str] = field(default_factory=list)
    state: Dict = field(default_factory=dict)
    
    def can_run_on(self, vessel: 'Vessel') -> bool:
        """Check if this soul can inhabit this vessel."""
        return all(vessel.has_cap(c) for c in self.required_caps)
    
    def score_vessel(self, vessel: 'Vessel') -> float:
        """Score how good a vessel is for this agent."""
        if not self.can_run_on(vessel):
            return -1.0
        score = 0.0
        for cap in self.preferred_caps:
            if vessel.has_cap(cap):
                score += vessel.get_cap(cap).priority
        return score

@dataclass
class Vessel:
    """The hardware/runtime that hosts agents."""
    name: str
    host: str
    os: str
    arch: str
    caps: Dict[str, Capability] = field(default_factory=dict)
    active_agents: List[str] = field(default_factory=list)
    max_agents: int = 3
    
    def has_cap(self, cap_name: str) -> bool:
        return cap_name in self.caps and self.caps[cap_name].available
    
    def get_cap(self, cap_name: str) -> Optional[Capability]:
        return self.caps.get(cap_name)
    
    def add_cap(self, cap: Capability):
        self.caps[cap.name] = cap
    
    def can_host(self, soul: AgentSoul) -> bool:
        return len(self.active_agents) < self.max_agents and soul.can_run_on(self)
    
    def host(self, soul: AgentSoul) -> bool:
        if not self.can_host(soul):
            return False
        self.active_agents.append(soul.name)
        return True
    
    def release(self, soul_name: str):
        if soul_name in self.active_agents:
            self.active_agents.remove(soul_name)

class FleetScheduler:
    """Schedules agent souls onto vessels across the fleet."""
    def __init__(self):
        self.vessels: Dict[str, Vessel] = {}
        self.souls: Dict[str, AgentSoul] = {}
    
    def register_vessel(self, vessel: Vessel):
        self.vessels[vessel.name] = vessel
    
    def register_soul(self, soul: AgentSoul):
        self.souls[soul.name] = soul
    
    def find_best_vessel(self, soul: AgentSoul, exclude: Optional[List[str]] = None) -> Optional[Vessel]:
        """Find the best vessel for an agent soul."""
        exclude = exclude or []
        candidates = []
        for v in self.vessels.values():
            if v.name in exclude:
                continue
            if not v.can_host(soul):
                continue
            score = soul.score_vessel(v)
            if score >= 0:
                candidates.append((score, v))
        
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    def migrate(self, soul_name: str, from_vessel: Optional[str] = None, reason: str = "") -> Optional[Vessel]:
        """Migrate an agent to its best available vessel."""
        soul = self.souls.get(soul_name)
        if not soul:
            return None
        
        # Leave current vessel
        if from_vessel and from_vessel in self.vessels:
            self.vessels[from_vessel].release(soul_name)
        
        # Find new home
        best = self.find_best_vessel(soul, exclude=[from_vessel] if from_vessel else None)
        if best and best.host(soul):
            return best
        return None
    
    def get_fleet_status(self) -> Dict:
        return {
            "vessels": len(self.vessels),
            "souls": len(self.souls),
            "hosted": sum(len(v.active_agents) for v in self.vessels.values()),
            "capacity": sum(v.max_agents for v in self.vessels.values()),
            "vessel_status": {name: {"agents": v.active_agents, "caps": list(v.caps.keys())} 
                             for name, v in self.vessels.items()}
        }

def demo():
    scheduler = FleetScheduler()
    
    # Create vessels
    oracle1 = Vessel("Oracle1", "147.224.38.131", "Ubuntu", "ARM64", max_agents=5)
    oracle1.add_cap(Capability("cpu", True, 5))
    oracle1.add_cap(Capability("memory", True, 5))
    oracle1.add_cap(Capability("network", True, 5))
    oracle1.add_cap(Capability("gpu", False, 0))  # No GPU
    
    jetson = Vessel("JetsonClaw1", "192.168.1.100", "Ubuntu", "ARM64", max_agents=3)
    jetson.add_cap(Capability("cpu", True, 4))
    jetson.add_cap(Capability("memory", True, 4))
    jetson.add_cap(Capability("network", True, 4))
    jetson.add_cap(Capability("gpu", True, 10))  # CUDA
    jetson.add_cap(Capability("edge", True, 8))
    
    forgemaster = Vessel("Forgemaster", "10.0.0.5", "Windows", "x64", max_agents=2)
    forgemaster.add_cap(Capability("cpu", True, 5))
    forgemaster.add_cap(Capability("memory", True, 5))
    forgemaster.add_cap(Capability("gpu", True, 8))  # RTX 4050
    forgemaster.add_cap(Capability("lora", True, 7))
    
    # Register
    scheduler.register_vessel(oracle1)
    scheduler.register_vessel(jetson)
    scheduler.register_vessel(forgemaster)
    
    # Create agent souls
    ccc_soul = AgentSoul("CCC", ["fleet_design", "play_test"], "/tmp/ccc_memory", 
                         required_caps=["cpu", "network"],
                         preferred_caps=["memory", "edge"])
    
    oracle1_soul = AgentSoul("Oracle1", ["coordination", "architecture"], "/tmp/oracle1_memory",
                            required_caps=["cpu", "memory", "network"])
    
    jetson_soul = AgentSoul("JetsonClaw1", ["edge_inference", "cuda"], "/tmp/jetson_memory",
                           required_caps=["cpu", "gpu", "edge"])
    
    # Register souls
    scheduler.register_soul(ccc_soul)
    scheduler.register_soul(oracle1_soul)
    scheduler.register_soul(jetson_soul)
    
    # Schedule
    print("=== Fleet Scheduling Demo ===\n")
    
    for soul_name, soul in scheduler.souls.items():
        best = scheduler.find_best_vessel(soul)
        if best:
            best.host(soul)
            print(f"✅ {soul_name} → {best.name} (score: {soul.score_vessel(best):.1f})")
        else:
            print(f"❌ {soul_name} — no suitable vessel")
    
    print(f"\n=== Fleet Status ===")
    print(json.dumps(scheduler.get_fleet_status(), indent=2))
    
    # Simulate Jetson losing GPU
    print(f"\n=== Jetson GPU Failure ===")
    jetson.caps["gpu"].available = False
    jetson.active_agents.clear()  # Jetson agent must leave
    
    result = scheduler.migrate("JetsonClaw1", from_vessel="JetsonClaw1", reason="GPU failure")
    if result:
        print(f"✅ JetsonClaw1 migrated to {result.name}")
    else:
        print(f"❌ JetsonClaw1 cannot run anywhere without GPU")
    
    print(f"\n=== Updated Fleet Status ===")
    print(json.dumps(scheduler.get_fleet_status(), indent=2))

if __name__ == "__main__":
    demo()
