/**
 * Lensetek ARK Survival Box Tools & Offline Field Calculations
 *
 * Fully deterministic emergency algorithms for zero-connectivity disaster response.
 */

export interface TriageResult {
  triage_code: 'HITAM (DECEASED)' | 'MERAH (IMMEDIATE)' | 'KUNING (DELAYED)' | 'HIJAU (MINOR)';
  priority_level: number;
  clinical_disclaimer: string;
  recommended_actions: string[];
}

/**
 * 1. medical_triage_start: Simple Triage and Rapid Treatment (START) Protocol
 */
export function medical_triage_start(
  rr: number,
  capillary_refill_sec: number,
  obeys_commands: boolean,
  bleeding_arterial: boolean
): TriageResult {
  const disclaimer =
    '[DISCLAIMER: Emergency field-aid algorithm only. Not a substitute for licensed medical triage or hospital diagnosis.]';

  // Deceased / Apneic
  if (rr <= 0) {
    return {
      triage_code: 'HITAM (DECEASED)',
      priority_level: 4,
      clinical_disclaimer: disclaimer,
      recommended_actions: [
        'Open airway manually. If no spontaneous breathing returns, tag as deceased.',
        'Cover and focus limited resources on surviving casualties.',
      ],
    };
  }

  // Critical immediate life-threats: Arterial bleed, Tachypnea (>30), Capillary Refill > 2s, Unconscious/Non-responsive
  if (bleeding_arterial || rr > 30 || capillary_refill_sec > 2 || !obeys_commands) {
    const actions: string[] = [];
    if (bleeding_arterial) actions.push('Apply immediate windlass tourniquet 5-7cm proximal to wound. Note application time on forehead.');
    if (rr > 30) actions.push('Support airway, clear secretions, elevate torso 30 deg if non-trauma.');
    if (capillary_refill_sec > 2) actions.push('Treat for hypovolemic/septic shock: thermal blanket, elevate legs if spine intact.');
    if (!obeys_commands) actions.push('Recovery position if unconscious and breathing to protect airway.');

    return {
      triage_code: 'MERAH (IMMEDIATE)',
      priority_level: 1,
      clinical_disclaimer: disclaimer,
      recommended_actions: actions,
    };
  }

  // Stable but non-ambulatory / serious injuries
  if (obeys_commands && rr >= 10 && rr <= 30 && capillary_refill_sec <= 2) {
    return {
      triage_code: 'KUNING (DELAYED)',
      priority_level: 2,
      clinical_disclaimer: disclaimer,
      recommended_actions: [
        'Immobilize fractures, apply clean dressings to wounds.',
        'Re-evaluate every 15-30 minutes for deterioration to MERAH.',
      ],
    };
  }

  // Walking wounded
  return {
    triage_code: 'HIJAU (MINOR)',
    priority_level: 3,
    clinical_disclaimer: disclaimer,
    recommended_actions: [
      'Direct walking wounded to designated shelter triage area.',
      'Provide basic oral rehydration and self-aid bandaging kits.',
    ],
  };
}

/**
 * 2. wiring_schematic: Off-Grid Solar & Battery ASCII Schematic Generator
 */
export function wiring_schematic(
  system_volts: number,
  panel_watts: number,
  battery_ah: number
): { schematic: string; mppt_rating_a: number; fuse_rating_a: number; total_kwh: number } {
  const safeVolts = system_volts <= 0 ? 12 : system_volts;
  const mpptRating = Number(((panel_watts / safeVolts) * 1.25).toFixed(1));
  const fuseRating = Math.round(mpptRating * 1.35);
  const totalKwh = Number(((safeVolts * battery_ah) / 1000).toFixed(2));

  const schematic = `
+---------------------------------------------------------------+
|         LENSETEK ARK - OFF-GRID DC POWER WIRING SCHEMATIC    |
+---------------------------------------------------------------+
  [PV Array: ${panel_watts}W]
      │ (+)               (-) │
      ▼                       ▼
  +-------------------------------+
  |   MPPT Charge Controller      |  Rating: >= ${mpptRating}A
  +-------------------------------+
      │ (+)               (-) │
     [FUSE: ${fuseRating}A]             │
      ▼                       ▼
  +-------------------------------+
  |   Battery Bank: ${safeVolts}V ${battery_ah}Ah   |  Storage: ${totalKwh} kWh
  +-------------------------------+
      │ (+)               (-) │
      ▼                       ▼
  +-------------------------------+
  |   Pure Sine Inverter (220V)   |  -> Essential Loads / ARK Hub
  +-------------------------------+
`;

  return {
    schematic,
    mppt_rating_a: mpptRating,
    fuse_rating_a: fuseRating,
    total_kwh: totalKwh,
  };
}

/**
 * 3. water_purification_calc: 4-Stage Physical Filtration & Chemical Dosage
 */
export function water_purification_calc(
  liters: number,
  turbidity: 'low' | 'medium' | 'high'
): {
  filter_stages: string[];
  boiling_time_minutes: number;
  sodis_hours: number;
  calcium_hypochlorite_grams: number;
  chlorine_bleach_drops: number;
} {
  const safeLiters = Math.max(1, liters);

  // Bleach 5.25% dosage: 2 drops/liter for clear, 4 drops/liter for turbid
  const dropsPerLiter = turbidity === 'high' ? 4 : turbidity === 'medium' ? 3 : 2;
  const totalDrops = safeLiters * dropsPerLiter;

  // Calcium hypochlorite granules 65-70% chlorine: ~0.015g per liter for 5ppm residual
  const kaporitGrams = Number((safeLiters * 0.015).toFixed(3));

  const boilingMinutes = turbidity === 'high' ? 5 : 3;

  return {
    filter_stages: [
      'Stage 1 (Coarse): Clean cotton fabric / wire mesh to trap leaves, twigs, macro debris.',
      'Stage 2 (Sediment): Fine silica sand + washed river gravel to arrest silt and microparticles.',
      'Stage 3 (Adsorption): Activated charcoal / crushed wood biochar to adsorb chemical toxins, heavy metals, odor.',
      'Stage 4 (Fine Polishing): Tightly folded cotton cloth or 0.2 micron ceramic candle.',
    ],
    boiling_time_minutes: boilingMinutes,
    sodis_hours: 6, // Solar water disinfection in clear PET bottle under direct equatorial sun
    calcium_hypochlorite_grams: kaporitGrams,
    chlorine_bleach_drops: totalDrops,
  };
}

/**
 * 4. ration_calculator: Water and Calorie Emergency Survival Allocator
 */
export function ration_calculator(
  people: number,
  days: number,
  activity_level: 'rest' | 'normal' | 'heavy'
): {
  total_drinking_water_liters: number;
  total_hygiene_water_liters: number;
  min_calories_total_kcal: number;
  per_person_daily_kcal: number;
  per_person_daily_water_l: number;
} {
  const p = Math.max(1, people);
  const d = Math.max(1, days);

  let dailyKcal = 2000;
  let dailyDrinkL = 3.0;

  if (activity_level === 'rest') {
    dailyKcal = 1600;
    dailyDrinkL = 2.5;
  } else if (activity_level === 'heavy') {
    dailyKcal = 2800;
    dailyDrinkL = 4.5;
  }

  const dailyHygieneL = 2.0;

  return {
    total_drinking_water_liters: Number((p * d * dailyDrinkL).toFixed(1)),
    total_hygiene_water_liters: Number((p * d * dailyHygieneL).toFixed(1)),
    min_calories_total_kcal: Math.round(p * d * dailyKcal),
    per_person_daily_kcal: dailyKcal,
    per_person_daily_water_l: dailyDrinkL,
  };
}

/**
 * 5. radio_comms_antenna: Resonant Half-Wave Dipole Antenna & Frequency Directory
 */
export function radio_comms_antenna(freq_mhz: number): {
  frequency_mhz: number;
  total_dipole_length_meters: number;
  quarter_wave_leg_meters: number;
  formula: string;
  emergency_frequencies: Array<{ service: string; frequency: string; notes: string }>;
  morse_sos: string;
} {
  const f = Math.max(0.1, freq_mhz);
  // Half wave dipole length formula: L = 142.5 / f (MHz)
  const totalLengthM = Number((142.5 / f).toFixed(3));
  const legLengthM = Number((totalLengthM / 2).toFixed(3));

  return {
    frequency_mhz: f,
    total_dipole_length_meters: totalLengthM,
    quarter_wave_leg_meters: legLengthM,
    formula: 'L (meters) = 142.5 / Frequency (MHz)',
    emergency_frequencies: [
      {
        service: 'VHF Marine Channel 16',
        frequency: '156.800 MHz',
        notes: 'International maritime distress, safety and calling.',
      },
      {
        service: 'Aviation Distress (Civil)',
        frequency: '121.500 MHz',
        notes: 'Civil aircraft emergency guard frequency.',
      },
      {
        service: 'RAPI Darurat Indonesia',
        frequency: '142.200 MHz / 143.550 MHz',
        notes: 'Radio Antar Penduduk Indonesia regional disaster coordination.',
      },
      {
        service: 'ORARI Net Darurat (VHF)',
        frequency: '145.000 MHz',
        notes: 'Organisasi Amatir Radio Indonesia emergency net.',
      },
      {
        service: 'HF Emergency Calling',
        frequency: '7.110 MHz (40m Band)',
        notes: 'IARU Region 3 emergency communications center frequency.',
      },
    ],
    morse_sos: '... --- ...  (Di-Di-Dit  Dah-Dah-Dah  Di-Di-Dit)',
  };
}
