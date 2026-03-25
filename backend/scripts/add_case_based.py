"""
Phase 4 bootstrap: add one case_based (4m) question per physics chapter.
Run once: python -m backend.scripts.add_case_based
"""
import json
import sqlite3
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "questions"
DB_PATH  = Path(__file__).parent.parent.parent / "data" / "science_assessor.db"

CB_QUESTIONS = [
    {
        "chapter": "light",
        "topic": "refraction",
        "id": "light_cb_001",
        "text": (
            "Riya tries to see a coin at the bottom of an empty bowl but cannot see it from her seat. "
            "Her friend slowly pours water into the bowl, and the coin becomes visible without Riya moving.\n\n"
            "(a) Name the phenomenon responsible for this observation. [1]\n"
            "(b) In which direction does light bend when it enters water from air? [1]\n"
            "(c) Draw a labelled ray diagram showing how light from the coin reaches Riya's eye. [2]"
        ),
        "type": "case_based",
        "marks": 4,
        "difficulty": 3,
        "board_weightage": 0.15,
        "options": None,
        "rubric": {
            "keywords": ["refraction", "refractive index", "bending", "normal", "denser"],
            "key_points": [
                "Refraction of light is the phenomenon responsible",
                "Light bends towards the normal when entering denser medium (water)",
                "Ray diagram shows light bending at water-air interface from coin to eye",
                "Correct labelling: incident ray, refracted ray, normal, interface"
            ],
            "expected_answer": "(a) Refraction of light. (b) Towards the normal — water is denser than air. (c) Ray diagram showing light from coin bending at water surface towards Riya's eye.",
            "formula": None,
            "diagram_required": True,
            "diagram_checklist": ["incident ray", "refracted ray", "normal", "interface"],
            "partial_marks": {}
        },
        "template_params": None,
        "diagram_path": None,
    },
    {
        "chapter": "human_eye",
        "topic": "defects_of_vision",
        "id": "human_eye_cb_001",
        "text": (
            "Suresh (60 yrs) holds his newspaper at arm's length to read it. His doctor prescribes +2.5 D lenses. "
            "His grandson Rahul (14 yrs) cannot see the blackboard clearly but reads books without difficulty.\n\n"
            "(a) Name the defect Suresh suffers from. [1]\n"
            "(b) Name Rahul's defect and the corrective lens used. [1]\n"
            "(c) Compare where the image forms on the retina in each case for distance vision. [2]"
        ),
        "type": "case_based",
        "marks": 4,
        "difficulty": 3,
        "board_weightage": 0.15,
        "options": None,
        "rubric": {
            "keywords": ["presbyopia", "hypermetropia", "myopia", "concave", "convex", "retina", "focal"],
            "key_points": [
                "Suresh has presbyopia (or hypermetropia) — corrected by convex lens",
                "Rahul has myopia — corrected by concave lens",
                "In hypermetropia image forms behind retina",
                "In myopia image forms in front of retina"
            ],
            "expected_answer": "(a) Presbyopia. (b) Myopia; concave lens. (c) In hypermetropia, parallel rays focus behind the retina; in myopia they focus in front of the retina.",
            "formula": None,
            "diagram_required": False,
            "diagram_checklist": [],
            "partial_marks": {}
        },
        "template_params": None,
        "diagram_path": None,
    },
    {
        "chapter": "electricity",
        "topic": "series_parallel",
        "id": "electricity_cb_001",
        "text": (
            "Three resistors of 6 Ω, 3 Ω, and 2 Ω are connected in parallel across a 12 V battery. "
            "The wire connecting the 2 Ω resistor feels hotter than the others after a few minutes.\n\n"
            "(a) Calculate the equivalent resistance of the combination. [1]\n"
            "(b) Find the current through the 2 Ω resistor. [1]\n"
            "(c) Explain why the 2 Ω wire heats up more than the 6 Ω wire. [2]"
        ),
        "type": "case_based",
        "marks": 4,
        "difficulty": 3,
        "board_weightage": 0.15,
        "options": None,
        "rubric": {
            "keywords": ["parallel", "equivalent resistance", "Ohm", "current", "heating", "H = I2Rt", "power"],
            "key_points": [
                "1/Req = 1/6 + 1/3 + 1/2 = 1 Ω",
                "Current through 2 Ω = 12/2 = 6 A",
                "Current through 6 Ω = 12/6 = 2 A; higher current in 2 Ω",
                "H = I²Rt — greater current produces more heat in same time"
            ],
            "expected_answer": "(a) Req = 1 Ω. (b) I = 12/2 = 6 A. (c) In parallel all have same voltage (12 V); 2 Ω carries 6 A vs 2 A through 6 Ω. Since H = I²Rt, the 2 Ω wire dissipates more heat.",
            "formula": "1/Req = 1/R1 + 1/R2 + 1/R3",
            "diagram_required": False,
            "diagram_checklist": [],
            "partial_marks": {}
        },
        "template_params": None,
        "diagram_path": None,
    },
    {
        "chapter": "magnetic_effects",
        "topic": "electric_motor",
        "id": "magnetic_effects_cb_001",
        "text": (
            "An electric motor in a mixer grinder is protected by a 5 A circuit breaker. "
            "The motor spins in reverse when the battery terminals are swapped.\n\n"
            "(a) State the principle on which an electric motor works. [1]\n"
            "(b) Name the rule that determines the direction of motion of the motor coil. [1]\n"
            "(c) State two ways to increase the rotational speed of the motor. [2]"
        ),
        "type": "case_based",
        "marks": 4,
        "difficulty": 3,
        "board_weightage": 0.15,
        "options": None,
        "rubric": {
            "keywords": ["Fleming left hand rule", "magnetic force", "current", "coil", "commutator", "speed"],
            "key_points": [
                "Motor works on: current-carrying conductor in magnetic field experiences mechanical force",
                "Fleming's Left Hand Rule gives direction of force/motion",
                "Increase speed: increase current OR increase magnetic field strength OR increase number of coil turns",
                "Commutator reverses current direction every half turn to maintain continuous rotation"
            ],
            "expected_answer": "(a) A current-carrying conductor placed in a magnetic field experiences a force. (b) Fleming's Left Hand Rule. (c) Increase current; increase strength of magnetic field (use stronger magnets); increase number of turns in the armature coil.",
            "formula": "F = BIL",
            "diagram_required": False,
            "diagram_checklist": [],
            "partial_marks": {}
        },
        "template_params": None,
        "diagram_path": None,
    },
    {
        "chapter": "sources_of_energy",
        "topic": "solar_energy",
        "id": "sources_of_energy_cb_001",
        "text": (
            "A village installs a 500 kW solar plant generating power 9 AM–5 PM. Output drops 80% on cloudy days. "
            "They also use a biogas plant fed with cattle dung.\n\n"
            "(a) State one advantage and one limitation of solar energy. [2]\n"
            "(b) Write the overall reaction in a biogas plant. [1]\n"
            "(c) Why is biogas a cleaner fuel than directly burning dung cakes? [1]"
        ),
        "type": "case_based",
        "marks": 4,
        "difficulty": 3,
        "board_weightage": 0.15,
        "options": None,
        "rubric": {
            "keywords": ["solar", "renewable", "biogas", "methane", "CH4", "anaerobic", "clean", "smoke"],
            "key_points": [
                "Advantage: renewable/inexhaustible, non-polluting",
                "Limitation: intermittent (unavailable at night, reduced on cloudy days)",
                "Biogas: organic matter → CH4 + CO2 + H2O (anaerobic decomposition)",
                "Biogas burns completely; dung cakes produce smoke/toxic gases causing pollution"
            ],
            "expected_answer": "(a) Advantage: renewable, no pollution. Limitation: intermittent—unavailable at night and reduced on cloudy days. (b) Organic matter (dung) undergoes anaerobic decomposition: complex organics → CH4 + CO2 + H2O. (c) Biogas burns completely producing CO2 and water; burning dung cakes produces smoke, soot and CO causing air pollution.",
            "formula": None,
            "diagram_required": False,
            "diagram_checklist": [],
            "partial_marks": {}
        },
        "template_params": None,
        "diagram_path": None,
    },
]


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    added_json = 0
    added_db = 0

    for q in CB_QUESTIONS:
        chapter = q["chapter"]
        qid = q["id"]

        # ── Update JSON ────────────────────────────────────────────────────
        jf = DATA_DIR / f"{chapter}.json"
        if jf.exists():
            data = json.loads(jf.read_text(encoding="utf-8"))
            data["questions"] = [x for x in data["questions"] if x["id"] != qid]
            # Strip metadata keys before storing in JSON
            json_q = {k: v for k, v in q.items() if k not in ("chapter", "topic", "difficulty", "board_weightage")}
            data["questions"].append(json_q)
            jf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            added_json += 1
        else:
            print(f"  WARNING: {jf} not found — skipping JSON update")

        # ── Upsert question_index ──────────────────────────────────────────
        conn.execute(
            """INSERT OR REPLACE INTO question_index
               (id, chapter, topic, type, difficulty, marks, board_weightage,
                source, has_diagram, has_template, times_served, approved)
               VALUES (?,?,?,?,?,?,?,'Phase4-CB',?,0,0,1)""",
            [
                qid, chapter, q["topic"], q["type"], q["difficulty"],
                q["marks"], q["board_weightage"],
                1 if q["rubric"].get("diagram_required") else 0,
            ],
        )
        added_db += 1
        print(f"  + {qid}  ({chapter})")

    conn.commit()
    conn.close()
    print(f"\nDone: {added_json} JSON updated, {added_db} rows in question_index.")


if __name__ == "__main__":
    main()
