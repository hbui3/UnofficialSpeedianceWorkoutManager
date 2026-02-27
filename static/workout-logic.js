/**
 * workout-logic.js
 * Pure functions for workout building logic — no DOM, no API calls.
 * Used by: create.html (via <script src>) and tests/workout-logic.test.mjs (via require).
 */

// ---------------------------------------------------------------------------
// Preset definitions
// ---------------------------------------------------------------------------
const PRESET_RULES = {
    '-1': { // Custom (KG / LBS depending on userUnit)
        label: 'KG', step: 0.5,
        defW: 10, minW: 1, maxW: 100,
        defR: 10, minR: 1, maxR: 99,
        defRest: 60, minRest: 0, maxRest: 300
    },
    '1': { // Gain Muscle (RM)
        label: 'RM', step: 1,
        defW: 13, minW: 9, maxW: 13,
        defR: 12, minR: 8, maxR: 12,
        defRest: 60, minRest: 45, maxRest: 120
    },
    '3': { // Stamina (RM)
        label: 'RM', step: 1,
        defW: 17, minW: 15, maxW: 20,
        defR: 15, minR: 13, maxR: 20,
        defRest: 45, minRest: 30, maxRest: 180
    },
    '5': { // Strength (RM)
        label: 'RM', step: 1,
        defW: 7, minW: 4, maxW: 9,
        defR: 6, minR: 2, maxR: 8,
        defRest: 90, minRest: 60, maxRest: 180
    }
};

/**
 * Returns effective rules for an exercise given the current unit.
 * @param {Object} ex - exercise object with selectedPresetId and isUnilateral
 * @param {number} userUnit - 0=Metric, 1=Imperial
 */
function getRules(ex, userUnit) {
    let rules = PRESET_RULES[String(ex.selectedPresetId)] || PRESET_RULES['-1'];
    if (ex.selectedPresetId == -1) {
        rules = Object.assign({}, rules); // clone
        if (userUnit === 1) {
            // Imperial (LBS)
            rules.label = 'LBS';
            rules.step = 1;
            if (ex.isUnilateral) {
                rules.maxW = 110;
                rules.minW = 8;
            } else {
                rules.maxW = 220;
                rules.minW = 15;
            }
        } else {
            // Metric (KG)
            // Unilateral (one cable): min 3.5 kg
            // Barbell (both cables joined via barbell attachment): min 7 kg (2 × 3.5 kg)
            // Dual-handle with separate cables: min 3.5 kg
            rules.step = 0.5;
            if (ex.isUnilateral) {
                rules.maxW = 50;
                rules.minW = 3.5;
            } else if (ex.isBarbell) {
                rules.maxW = 100;
                rules.minW = 7;
            } else {
                rules.maxW = 100;
                rules.minW = 3.5;
            }
        }
    }
    return rules;
}

/**
 * Clamp a value between min and max, then snap to nearest step.
 * @param {number} val
 * @param {number} min
 * @param {number} max
 * @param {number} step
 * @returns {number}
 */
function validateAndClamp(val, min, max, step) {
    if (isNaN(val)) val = min;
    val = Math.max(min, Math.min(max, val));
    if (step && step > 0) {
        val = Math.round(val / step) * step;
        // Floating-point fix: round to same number of decimals as step
        const decimals = (step.toString().split('.')[1] || '').length;
        val = parseFloat(val.toFixed(decimals));
    }
    return val;
}

/**
 * Convert LBS to KG, rounded to nearest 0.5 kg.
 * @param {number} lbs
 * @returns {number}
 */
function lbsToKg(lbs) {
    const kg = lbs / 2.2;
    return Math.round(kg * 2) / 2;
}

/**
 * Convert KG to LBS, rounded to nearest integer lb.
 * @param {number} kg
 * @returns {number}
 */
function kgToLbs(kg) {
    return Math.round(parseFloat(kg) * 2.2);
}

/**
 * Expand/not-expand sets for a unilateral exercise based on import context.
 * @param {Array} sets - array of set objects from imported JSON
 * @param {boolean} isUnilateral
 * @param {boolean} alreadyExpanded - true if L/R pairs are already present (app export)
 * @returns {Array}
 */
function parseImportedSets(sets, isUnilateral, alreadyExpanded) {
    if (isUnilateral && !alreadyExpanded) {
        const out = [];
        sets.forEach(s => {
            out.push(Object.assign({}, s)); // Left
            out.push(Object.assign({}, s)); // Right
        });
        return out;
    }
    return sets.map(s => Object.assign({}, s));
}

/**
 * Build the JSON export object from workoutData.
 * @param {Array} workoutData
 * @param {string} planName
 * @returns {Object}
 */
function buildExportJSON(workoutData, planName) {
    return {
        name: planName || 'Custom Workout',
        exercises: workoutData.map(ex => ({
            id: ex.groupId,
            title: ex.title,
            preset: ex.selectedPresetId,
            isUnilateralExpanded: ex.isUnilateral ? true : false,
            sets: ex.sets.map(s => ({
                reps: s.reps,
                weight: s.weight,
                mode: s.mode,
                rest: s.rest
            }))
        }))
    };
}

// ---------------------------------------------------------------------------
// Export for Node.js (tests) and browser (WorkoutLogic namespace)
// ---------------------------------------------------------------------------
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PRESET_RULES, getRules, validateAndClamp, lbsToKg, kgToLbs, parseImportedSets, buildExportJSON };
} else if (typeof window !== 'undefined') {
    // Use a namespace to avoid colliding with identically-named functions in create.html
    window.WorkoutLogic = { PRESET_RULES, getRules, validateAndClamp, lbsToKg, kgToLbs, parseImportedSets, buildExportJSON };
}
