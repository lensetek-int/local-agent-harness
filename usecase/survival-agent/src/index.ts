/**
 * Lensetek ARK Survival Box AI Agent Harness
 *
 * Rugged terminal HUD with deterministic emergency calculations.
 */

import {
  medical_triage_start,
  wiring_schematic,
  water_purification_calc,
  ration_calculator,
  radio_comms_antenna,
} from './survival_tools.js';

const GREEN = '\x1b[32m';
const BOLD = '\x1b[1m';
const RESET = '\x1b[0m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';

function printHeader(): void {
  console.log(`${GREEN}${BOLD}`);
  console.log('╔═════════════════════════════════════════════════════════════════╗');
  console.log('║        LENSETEK ARK - RUGGED SURVIVAL BOX AGENT HUD (AIR-GAPPED)║');
  console.log('║        OFFLINE SYSTEM-2 REASONING & EMERGENCY PROTOCOLS         ║');
  console.log('╚═════════════════════════════════════════════════════════════════╝');
  console.log(`${RESET}`);
}

async function runSelfTest(): Promise<void> {
  printHeader();
  console.log(`${GREEN}[SELF-TEST] Initializing deterministic field calculation suites...${RESET}\n`);

  // 1. Triage Test
  console.log(`${GREEN}[TEST 1/5] Medical START Triage Algorithm:${RESET}`);
  const redCasualty = medical_triage_start(34, 3, false, true);
  console.log(` -> Casualty 1: ${RED}${redCasualty.triage_code}${RESET} (Priority: ${redCasualty.priority_level})`);
  if (!redCasualty.triage_code.includes('MERAH')) throw new Error('START triage failed for critical case');

  const yellowCasualty = medical_triage_start(18, 1.5, true, false);
  console.log(` -> Casualty 2: ${YELLOW}${yellowCasualty.triage_code}${RESET} (Priority: ${yellowCasualty.priority_level})`);
  if (!yellowCasualty.triage_code.includes('KUNING')) throw new Error('START triage failed for yellow case');

  // 2. Solar Wiring Test
  console.log(`\n${GREEN}[TEST 2/5] Off-Grid Solar Wiring Schematic:${RESET}`);
  const wiring = wiring_schematic(24, 400, 200);
  console.log(` -> Solar 400W @ 24V: MPPT Rating = ${wiring.mppt_rating_a}A | Fuse = ${wiring.fuse_rating_a}A | Storage = ${wiring.total_kwh} kWh`);
  if (wiring.mppt_rating_a <= 0 || wiring.fuse_rating_a <= 0) throw new Error('Wiring calculator returned invalid ratings');

  // 3. Water Purification Test
  console.log(`\n${GREEN}[TEST 3/5] Water Purification & Chemical Dosage:${RESET}`);
  const water = water_purification_calc(20, 'high');
  console.log(` -> 20L Turbid Water: Reboil = ${water.boiling_time_minutes} min | Bleach = ${water.chlorine_bleach_drops} drops | Kaporit = ${water.calcium_hypochlorite_grams}g`);
  if (water.boiling_time_minutes < 5 || water.chlorine_bleach_drops < 40) throw new Error('Water purifier calculation mismatch');

  // 4. Ration Calculator Test
  console.log(`\n${GREEN}[TEST 4/5] Survival Ration Allocator:${RESET}`);
  const rations = ration_calculator(4, 7, 'normal');
  console.log(` -> 4 People x 7 Days: Total Drinking Water = ${rations.total_drinking_water_liters} L | Total Calories = ${rations.min_calories_total_kcal} kcal`);
  if (rations.total_drinking_water_liters !== 84 || rations.min_calories_total_kcal !== 56000) {
    throw new Error('Ration calculator calculation mismatch');
  }

  // 5. Radio Antenna Dipole Test
  console.log(`\n${GREEN}[TEST 5/5] Radio Comms Resonant Dipole Length:${RESET}`);
  const radio = radio_comms_antenna(156.8); // Marine Ch 16
  console.log(` -> VHF Marine 156.800 MHz: Total Length = ${radio.total_dipole_length_meters}m (Leg: ${radio.quarter_wave_leg_meters}m)`);
  console.log(` -> SOS Morse: ${radio.morse_sos}`);
  if (Math.abs(radio.total_dipole_length_meters - 0.909) > 0.02) {
    throw new Error('Radio antenna dipole calculation mismatch');
  }

  console.log(`\n${GREEN}${BOLD}=================================================================`);
  console.log(' ✅ ALL 5 SURVIVAL TOOLS PASSED DETERMINISTIC SELF-TEST (100%)');
  console.log(`=================================================================${RESET}`);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) {
    await runSelfTest();
    process.exit(0);
  }

  printHeader();
  console.log(`${GREEN}[STATUS] Lensetek ARK Survival Agent Online. All modules ready.${RESET}`);
  console.log(`${GREEN}[INFO] Air-Gapped Mode: Active | SLM Endpoint: http://127.0.0.1:3000/v1${RESET}`);
  console.log(`${GREEN}[INFO] Execute with '--self-test' to run emergency calculation diagnostics.${RESET}`);
}

main().catch((err) => {
  console.error(`${RED}[ERROR] Lensetek ARK Agent crashed:${RESET}`, err);
  process.exit(1);
});
