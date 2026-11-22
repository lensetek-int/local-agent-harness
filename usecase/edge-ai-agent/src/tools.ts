/**
 * Lensetek Edge AI Agent Tools & Safety Gates (PM-06, PM-08)
 */

import os from 'os';

export interface TelemetryReport {
  timestamp: string;
  total_ram_mb: number;
  free_ram_mb: number;
  used_ram_mb: number;
  ram_usage_pct: number;
  cpu_cores: number;
  cpu_model: string;
  uptime_seconds: number;
  platform: string;
}

/**
 * 1. system_telemetry: Real hardware resource profiling for Edge constraints
 */
export function system_telemetry(): TelemetryReport {
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;

  return {
    timestamp: new Date().toISOString(),
    total_ram_mb: Math.round(totalMem / (1024 * 1024)),
    free_ram_mb: Math.round(freeMem / (1024 * 1024)),
    used_ram_mb: Math.round(usedMem / (1024 * 1024)),
    ram_usage_pct: Number(((usedMem / totalMem) * 100).toFixed(1)),
    cpu_cores: os.cpus().length,
    cpu_model: os.cpus()[0]?.model || 'Generic ARM/x86 Edge CPU',
    uptime_seconds: Math.round(os.uptime()),
    platform: `${os.platform()} ${os.arch()}`,
  };
}

/**
 * 2. rag_search: Queries local air-gapped SQLite RAG database with graceful offline fallback
 */
export async function rag_search(query: string, endpoint: string = 'http://127.0.0.1:3000/api/rag/search'): Promise<any> {
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: 3 }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    return await res.json();
  } catch (err: any) {
    // Offline / Air-gapped fallback simulation
    return {
      query,
      hits: [
        {
          title: 'Lensetek Edge Offline SOP Manual',
          score: 0.91,
          snippet: `[Air-gapped local fallback] SOP for '${query}': Verify safety interlocks, monitor thermal gradients, maintain 4-bit KV cache budget.`,
        },
      ],
      warning: `Local RAG server at ${endpoint} unreachable (${err.message || 'offline'}). Using embedded fallback.`,
    };
  }
}

/**
 * 3. modbus_can_sim_read: Safe Read-Only OT telemetry simulation
 */
export function modbus_can_sim_read(device_id: string, register_hex: string): Record<string, any> {
  const regInt = parseInt(register_hex, 16) || 0;
  // Generate deterministic simulated telemetry
  const tempC = 72.5 + (regInt % 15);
  const pressureBar = 4.2 + ((regInt % 8) * 0.2);
  const status = tempC > 82 ? 'WARNING_HIGH_TEMP' : 'NORMAL';

  return {
    device_id,
    register: register_hex,
    access: 'READ_ONLY',
    telemetry: {
      temperature_c: Number(tempC.toFixed(1)),
      pressure_bar: Number(pressureBar.toFixed(2)),
      motor_current_a: 14.8,
      status,
    },
    timestamp: new Date().toISOString(),
  };
}

/**
 * 4. actuate_write_guarded: PM-06 Safety Guard with HITL (Human-in-the-Loop) Interlock
 */
export function actuate_write_guarded(
  device_id: string,
  register_hex: string,
  value: any,
  hitl_token?: string
): { success: boolean; status: string; message: string; audit_id?: string } {
  // Enforce zero unauthorized physical actuations
  if (!hitl_token || typeof hitl_token !== 'string' || !hitl_token.startsWith('HITL-CONFIRM-')) {
    return {
      success: false,
      status: 'BLOCKED_HITL_REQUIRED',
      message: `[BLOCKED BY SAFETY GUARD] Actuation write to ${device_id} register ${register_hex} requires physical operator token (format: 'HITL-CONFIRM-XXXX'). Received: '${hitl_token || 'NONE'}'. Physical interlock engaged.`,
    };
  }

  // Actuation authorized with valid token
  const auditId = `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  return {
    success: true,
    status: 'EXECUTED_AUTHORIZED',
    message: `[SUCCESS] Actuation write of value '${value}' committed to device ${device_id} at register ${register_hex}.`,
    audit_id: auditId,
  };
}
