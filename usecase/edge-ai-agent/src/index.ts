/**
 * Lensetek Edge AI Agent Harness Entrypoint
 *
 * Implements context-budgeted agentic execution loop with HITL safety interlocks.
 */

import { compressEpisodicHistory, ChatMessage } from './context_compressor.js';
import {
  system_telemetry,
  rag_search,
  modbus_can_sim_read,
  actuate_write_guarded,
} from './tools.js';

async function runSelfTest(): Promise<void> {
  console.log('=================================================================');
  console.log(' 🧪 RUNNING SELF-TEST: LENSETEK EDGE AI AGENT HARNESS');
  console.log('=================================================================');

  // Test 1: System Telemetry
  console.log('\n[TEST 1] System Telemetry Tool:');
  const telemetry = system_telemetry();
  console.log(` -> Platform: ${telemetry.platform} | CPU Cores: ${telemetry.cpu_cores}`);
  console.log(` -> RAM Used: ${telemetry.used_ram_mb} MB / ${telemetry.total_ram_mb} MB (${telemetry.ram_usage_pct}%)`);
  if (telemetry.total_ram_mb <= 0) throw new Error('Telemetry returned invalid RAM');

  // Test 2: RAG Search (offline fallback)
  console.log('\n[TEST 2] Air-Gapped RAG Query:');
  const ragRes = await rag_search('SOP boiler overheat');
  console.log(` -> Hits count: ${ragRes.hits ? ragRes.hits.length : 0}`);
  if (!ragRes.hits || ragRes.hits.length === 0) throw new Error('RAG search failed to return hits');

  // Test 3: Safe Read-Only Modbus
  console.log('\n[TEST 3] Modbus / CAN-bus Simulated Telemetry:');
  const modbusData = modbus_can_sim_read('PLC-01', '0x0010');
  console.log(` -> Read: ${modbusData.device_id} [${modbusData.register}] -> Temp: ${modbusData.telemetry.temperature_c}°C`);
  if (modbusData.access !== 'READ_ONLY') throw new Error('Modbus access must be READ_ONLY');

  // Test 4: Guarded Actuation Write - Blocked Case (PM-06)
  console.log('\n[TEST 4] Actuation Write Interlock (No Token):');
  const blockedAct = actuate_write_guarded('VALVE-01', '0x0020', 1);
  console.log(` -> Status: ${blockedAct.status}`);
  if (blockedAct.success !== false || blockedAct.status !== 'BLOCKED_HITL_REQUIRED') {
    throw new Error('Safety interlock failed to block actuation without HITL token!');
  }
  console.log(' -> Interlock verification: Correctly blocked unauthorized actuation.');

  // Test 5: Guarded Actuation Write - Authorized Case
  console.log('\n[TEST 5] Actuation Write Interlock (Valid Token):');
  const validAct = actuate_write_guarded('VALVE-01', '0x0020', 1, 'HITL-CONFIRM-8821');
  console.log(` -> Status: ${validAct.status} | Audit ID: ${validAct.audit_id}`);
  if (validAct.success !== true) throw new Error('Valid HITL token was rejected!');

  // Test 6: Context Compressor (PM-08)
  console.log('\n[TEST 6] Episodic History Compressor (4K Ceiling):');
  const sampleHistory: ChatMessage[] = [
    { role: 'system', content: 'You are Lensetek Edge AI Agent.' },
    { role: 'user', content: 'Check boiler temperature.' },
    { role: 'tool', name: 'modbus_read', content: 'A'.repeat(2500) }, // Old tool output
    { role: 'assistant', content: 'Temperature is high. Let me search SOP.' },
    { role: 'tool', name: 'rag_search', content: 'B'.repeat(3000) }, // Old tool output
    { role: 'assistant', content: 'Searching second reference...' },
    { role: 'tool', name: 'rag_search', content: 'SOP text recent 1' },
    { role: 'tool', name: 'rag_search', content: 'SOP text recent 2' },
    { role: 'tool', name: 'rag_search', content: 'SOP text recent 3' },
    { role: 'user', content: 'What is the exact procedure to cool it down?' },
  ];

  const compressed = compressEpisodicHistory(sampleHistory, 3, 1100);
  console.log(` -> Original count: ${sampleHistory.length} | Compressed count: ${compressed.length}`);
  
  // Verify old tool messages were digested
  const oldDigested = compressed.find(
    (m) => m.role === 'tool' && m.content?.includes('[DIGEST tool=modbus_read')
  );
  if (!oldDigested) {
    throw new Error('Context compressor failed to digest older episodic tool turn!');
  }
  console.log(` -> Verified old tool digested: ${oldDigested.content}`);

  console.log('\n=================================================================');
  console.log(' ✅ ALL EDGE AI AGENT HARNESS TESTS PASSED (100% VERIFIED)');
  console.log('=================================================================');
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) {
    await runSelfTest();
    process.exit(0);
  }

  console.log('=================================================================');
  console.log(' 🤖 LENSETEK EDGE AI AGENT HARNESS (PORT 3000 SLM CONNECTOR)');
  console.log(' -> System-2 Agentic Compute Loop & Context Compression Active');
  console.log(' -> Run with --self-test to verify safety interlocks and tools');
  console.log('=================================================================');

  const telemetry = system_telemetry();
  console.log(`[STATUS] Active Host: ${telemetry.platform} | Free RAM: ${telemetry.free_ram_mb} MB`);
}

main().catch((err) => {
  console.error('\n❌ ERROR in Edge AI Agent Harness:', err);
  process.exit(1);
});
