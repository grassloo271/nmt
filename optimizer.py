import math
from pathlib import Path

import aerosandbox as asb
import aerosandbox.numpy as np
import casadi as ca
import pandas as pd

from wing_deflection import max_deflection


# ============================================================
# FILES
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent

POLAR_FILE = BACKEND_DIR / "naca2412_polar.csv"


# ============================================================
# AIRFOIL POLARS
# ============================================================

aero_df = pd.read_csv(POLAR_FILE)

alpha_array = aero_df["alpha"].to_numpy()
cl_array = aero_df["CL"].to_numpy()
cd_array = aero_df["CD"].to_numpy()
cm_array = aero_df["CM"].to_numpy()


CL_func = ca.interpolant(
    "CL_func",
    "bspline",
    [alpha_array],
    cl_array,
)

CD_func = ca.interpolant(
    "CD_func",
    "bspline",
    [alpha_array],
    cd_array,
)

CM_func = ca.interpolant(
    "CM_func",
    "bspline",
    [alpha_array],
    cm_array,
)


# ============================================================
# CONSTANTS
# ============================================================

wing_airfoil = asb.Airfoil("naca2412")
tail_airfoil = asb.Airfoil("naca0001")

E = 4e9
E_foam = 30e6

G_boom = E / 15

rho_balsa = 250
rho_foam = 30
rho_boom = 350

rho = 1.225
nu = 1.5e-5

pi = np.pi

def check_input_constraints(S, AR):

    violations = []
    satisfied = []

    b_total = math.sqrt(S * AR)
    b = b_total / 2
    c = S / b_total

    # ----------------------------------------
    # Minimum wing chord
    # ----------------------------------------

    residual = c - 0.15

    if residual < 0:
        violations.append({
            "name": "Minimum wing chord",
            "type": "input",
            "actual_residual": residual,
            "violation": -residual,
            "description":
                "Main wing chord must be greater than 0.150 m.",
        })
    else:
        satisfied.append({
            "name": "Minimum wing chord",
            "type": "input",
            "actual_residual": residual,
        })


    # ----------------------------------------
    # Maximum half-span
    # ----------------------------------------

    residual = 1.0 - b

    if residual < 0:
        violations.append({
            "name": "Maximum half-span",
            "type": "input",
            "actual_residual": residual,
            "violation": -residual,
            "description":
                "Main wing half-span must be less than 1.000 m.",
        })
    else:
        satisfied.append({
            "name": "Maximum half-span",
            "type": "input",
            "actual_residual": residual,
        })


    return {
        "violations": violations,
        "satisfied": satisfied,
        "n_violated": len(violations),
        "n_satisfied": len(satisfied),
        "feasible": len(violations) == 0,
    }

# ============================================================
# CONSTRAINT REPORTING
# ============================================================

def make_constraint_report(
    opti,
    constraints,
    tolerance=1e-6,
):
    """
    Evaluate the last optimizer iterate against every
    explicitly-defined design constraint.

    Every inequality is stored internally as:

        residual >= 0

    Every equality is stored internally as:

        residual == 0

    This makes it possible to calculate exactly how much
    each constraint is violated.
    """

    violations = []
    satisfied = []

    for constraint in constraints:

        name = constraint["name"]
        expression = constraint["expression"]
        constraint_type = constraint["type"]

        try:
            value = float(
                opti.debug.value(expression)
            )

        except Exception:
            try:
                value = float(
                    opti.value(expression)
                )
            except Exception:
                continue


        # ====================================================
        # INEQUALITY
        #
        # Feasible if residual >= 0
        # ====================================================

        if constraint_type == "inequality":

            residual = value

            if residual < -tolerance:

                violation = -residual

                violations.append({
                    "name": name,
                    "type": "inequality",
                    "actual_residual": residual,
                    "violation": violation,
                    "description": constraint["description"],
                })

            else:

                satisfied.append({
                    "name": name,
                    "type": "inequality",
                    "actual_residual": residual,
                })


        # ====================================================
        # EQUALITY
        #
        # Feasible if residual == 0
        # ====================================================

        elif constraint_type == "equality":

            residual = value

            if abs(residual) > tolerance:

                violations.append({
                    "name": name,
                    "type": "equality",
                    "actual_residual": residual,
                    "violation": abs(residual),
                    "description": constraint["description"],
                })

            else:

                satisfied.append({
                    "name": name,
                    "type": "equality",
                    "actual_residual": residual,
                })


    return {
        "violations": violations,
        "satisfied": satisfied,
        "n_violated": len(violations),
        "n_satisfied": len(satisfied),
        "feasible": len(violations) == 0,
    }


# ============================================================
# OPTIMIZER
# ============================================================

def optimize_aircraft(
    S: float,
    AR: float,
    margin: float
):
    input_report = check_input_constraints(S, AR)

    if not input_report["feasible"]:

        b_total = math.sqrt(S * AR)
        b = b_total / 2
        c = S / b_total

        return {
            "success": False,
            "status": "infeasible",
            "solver_status": "Not run",
            "solver_error": None,

            "constraints": {
                "feasible": False,
                "n_violated":
                    input_report["n_violated"],
                "n_satisfied":
                    input_report["n_satisfied"],
                "violations":
                    input_report["violations"],
                "satisfied":
                    input_report["satisfied"],
            },

            "wing": {
                "S": float(S),
                "AR": float(AR),
                "span": b_total,
                "chord": c,
                "dihedral": 10,
                "deflection": None,
            },

            "horizontal_tail": None,
            "vertical_tail": None,
            "performance": None,
            "stability": None,
        }
    """
    Optimize the aircraft around user-selected:

        S  = main-wing area [m^2]
        AR = main-wing aspect ratio [-]

    S and AR are fixed design inputs.

    Everything else is optimized around them.
    """


    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    if S <= 0:
        raise ValueError(
            "Wing area S must be positive."
        )

    if AR <= 0:
        raise ValueError(
            "Aspect ratio AR must be positive."
        )


    # ========================================================
    # OPTIMIZATION ENVIRONMENT
    # ========================================================

    opti = asb.Opti()


    # ========================================================
    # CONSTRAINT REGISTRY
    # ========================================================

    constraints = []


    def add_inequality(
        name,
        residual,
        description,
    ):
        """
        Add an inequality of the form:

            residual >= 0

        to both CasADi and our reporting system.
        """

        opti.subject_to(
            residual >= 0
        )

        constraints.append({
            "name": name,
            "type": "inequality",
            "expression": residual,
            "description": description,
        })


    def add_equality(
        name,
        residual,
        description,
    ):
        """
        Add an equality of the form:

            residual == 0
        """

        opti.subject_to(
            residual == 0
        )

        constraints.append({
            "name": name,
            "type": "equality",
            "expression": residual,
            "description": description,
        })


    # ========================================================
    # OPTIMIZED VARIABLES
    # ========================================================

    V = opti.variable(
        init_guess=4,
        lower_bound=0.1,
        upper_bound=20,
    )


    # S and AR are intentionally fixed user inputs.

    dihedral = 10

    dihedral_rad = (
        dihedral
        * np.pi
        / 180
    )


    AR_h = opti.variable(
        init_guess=5,
        lower_bound=4,
        upper_bound=6,
    )


    AR_v = opti.variable(
        # The original file used 3 here despite
        # the upper bound being 2. This is kept
        # inside the valid range for numerical robustness.
        init_guess=1.5,
        lower_bound=1,
        upper_bound=2,
    )


    S_h = opti.variable(
        init_guess=0.01,
        lower_bound=0.0001,
    )


    S_v = opti.variable(
        init_guess=0.005,
        lower_bound=0.0001,
    )


    H_loc = opti.variable(
        init_guess=0.7,
        lower_bound=0.6,
        upper_bound=0.9,
    )


    alpha = opti.variable(
        init_guess=5,
        lower_bound=0,
        upper_bound=15,
    )


    alpha_rad = (
        alpha
        * np.pi
        / 180
    )


    # ========================================================
    # MAIN WING GEOMETRY
    # ========================================================

    b_total = ca.sqrt(
        S * AR
    )

    c = S / b_total

    b = b_total / 2


    # Original:
    #
    # opti.subject_to(c > 0.15)
    #
    # equivalent:
    #
    # c - 0.15 >= 0

    add_inequality(
        "Minimum wing chord",
        c - 0.15,
        "Main wing chord must be greater than 0.150 m.",
    )


    # Original:
    #
    # opti.subject_to(b < 1)
    #
    # equivalent:
    #
    # 1 - b >= 0

    add_inequality(
        "Maximum half-span",
        1.0 - b,
        "Main wing half-span must be less than 1.000 m.",
    )


    # ========================================================
    # TAIL GEOMETRY
    # ========================================================

    b_h = (
        ca.sqrt(S_h * AR_h)
        / 2
    )

    c_h = (
        S_h
        / (b_h * 2)
    )


    b_v = ca.sqrt(
        S_v * AR_v
    )

    c_v = (
        S_v
        / b_v
    )


    # Original:
    #
    # opti.subject_to(c_v == c_h)

    add_equality(
        "Tail chord matching",
        c_v - c_h,
        "Vertical and horizontal tail chords must be equal.",
    )


    # ========================================================
    # MASS / CG VARIABLES
    # ========================================================

    COM = opti.variable(
        init_guess=0
    )


    weight = opti.variable(
        init_guess=0.1,
        lower_bound=0,
    )


    # ========================================================
    # TAIL VOLUME
    # ========================================================

    l_h = (
        H_loc
        - c / 4
        + c_h / 4
    )


    l_v = ca.sqrt(
        (
            H_loc
            - c / 4
            + c_v / 4
        ) ** 2
        + b_v ** 2
    )


    hor_vol_coef = (
        S_h
        * l_h
        / (S * c)
    )


    ver_vol_coef = (
        S_v
        * l_v
        / (S * b_total)
    )


    add_inequality(
        "Minimum horizontal tail volume",
        hor_vol_coef - 0.3,
        "Horizontal tail volume coefficient must be greater than 0.30.",
    )


    add_inequality(
        "Maximum horizontal tail volume",
        0.6 - hor_vol_coef,
        "Horizontal tail volume coefficient must be less than 0.60.",
    )


    add_inequality(
        "Minimum vertical tail volume",
        ver_vol_coef - 0.03,
        "Vertical tail volume coefficient must be greater than 0.03.",
    )


    add_inequality(
        "Maximum vertical tail volume",
        0.06 - ver_vol_coef,
        "Vertical tail volume coefficient must be less than 0.06.",
    )


    # ========================================================
    # AERODYNAMICS
    # ========================================================

    a0 = 2 * pi

    e = 0.9

    Re = V * c / nu


    cl_2d = CL_func(alpha)

    cd_2d = CD_func(alpha)

    cm_2d = CM_func(alpha)


    CL = (
        1
        / (
            1
            + a0
            / (pi * AR * e)
        )
        * cl_2d
    )


    # ========================================================
    # NEUTRAL POINT
    # ========================================================

    a_w = (
        a0
        / (
            1
            + a0
            / (pi * AR * e)
        )
    )


    a_h = a_w


    npt = (
        c
        * (
            S * a_w
            / (4 * S_h * a_h)
            + l_h / c
            + 0.25
        )
        / (
            S * a_w
            / (S_h * a_h)
            + 1
        )
    )


    add_equality(
        "Static margin",
        npt
        - COM
        - 0.2 * c,
        "Neutral point must be exactly 20% of mean chord ahead of the center of mass.",
    )


    # ========================================================
    # FORCES
    # ========================================================

    q = (
        0.5
        * rho
        * V ** 2
        * S
    )


    q_h = (
        0.5
        * rho
        * V ** 2
        * S_h
    )


    L = (
        q
        * CL
        * ca.cos(dihedral_rad)
    )


    # ========================================================
    # TAIL INCIDENCE
    # ========================================================

    i = opti.variable(
        init_guess=0
    )


    downwash = (
        2 * CL
        / (pi * AR)
    )


    i_alpha = (
        alpha_rad
        - downwash
        + i
    )


    CL_h = (
        i_alpha
        * a_h
    )


    L_h = (
        q_h
        * CL_h
    )


    # ========================================================
    # DRAG
    # ========================================================

    M = (
        q
        * cm_2d
        * c
    )


    CDi = (
        CL ** 2
        / (pi * AR * e)
    )


    CD_t = (
        CL_h ** 2
        / (pi * AR_h * e)
    )


    CD0 = (
        cd_2d
        + 0.023
    )


    CD = (
        CDi
        + CD0
    )


    D = (
        CD * q
        + CD_t * q_h
    )


    # ========================================================
    # PITCHING MOMENT / TRIM
    # ========================================================

    M_cg = (
        M
        + L * (
            COM
            - c / 4
        )
        - L_h * (
            H_loc
            + c_h / 4
            - COM
        )
    )


    add_equality(
        "Pitch trim",
        M_cg,
        "Net pitching moment about the center of mass must equal zero.",
    )


    # ========================================================
    # LIFT LIMITS
    # ========================================================

    add_inequality(
        "Main wing maximum CL",
        1.4 - CL,
        "Main wing lift coefficient must be less than 1.4.",
    )


    add_inequality(
        "Horizontal tail maximum CL",
        1.4 - CL_h,
        "Horizontal tail lift coefficient must be less than 1.4.",
    )


    # ========================================================
    # SPIRAL STABILITY
    # ========================================================

    spiral = (
        l_v
        * dihedral
        / (b_total * CL)
    )


    add_inequality(
        "Spiral stability",
        spiral - 5,
        "Spiral stability criterion must be greater than 5.",
    )


    # ========================================================
    # L/D
    # ========================================================

    L_over_D = L / D


    add_inequality(
        "Minimum L/D",
        L_over_D - 5,
        "Lift-to-drag ratio must be greater than 5.",
    )


    # ========================================================
    # RUDDER EFFECTIVENESS
    # ========================================================

    rudder_chord_frac = 0.2

    tau_rudder = 0.55

    a_v = a_w


    Cn_delta_r = (
        a_v
        * tau_rudder
        * (S_v * l_v)
        / (S * b_total)
    )


    add_inequality(
        "Rudder effectiveness",
        Cn_delta_r - 0.001,
        "Rudder effectiveness coefficient must be greater than 0.001.",
    )


    # ========================================================
    # STRUCTURAL / MASS CONSTANTS
    # ========================================================

    thickness = 0.002

    boom_area = 0.01 * 0.01

    boom_height = 0.01

    margin = margin


    I_formula = (
        lambda chord, tau:
        chord * thickness ** 3 / 12
    )


    battery_mass = 0.1

    motor_mass = 0.07

    radio = 0.02

    servos = 0.02


    # ========================================================
    # COMPONENT LOCATIONS
    # ========================================================

    batt_loc = opti.variable(
        init_guess=0
    )


    motor_loc = opti.variable(
        init_guess=-0.1,
        upper_bound=-0.05,
        lower_bound=-0.15,
    )


    add_inequality(
        "Battery behind motor",
        batt_loc - motor_loc,
        "Battery location must be behind the motor location.",
    )


    # ========================================================
    # MASS
    # ========================================================

    mass_wing = (
        S
        * rho_foam
        * (0.12 * 0.3 * c)
    )


    mass_h_stab = (
        S_h
        * thickness
        * rho_balsa
    )


    mass_v_stab = (
        S_v
        * thickness
        * rho_balsa
    )


    mass_boom = (
        (H_loc - motor_loc)
        * rho_boom
        * boom_area
    )


    mass_battery = battery_mass
    mass_motor = motor_mass
    mass_radio = radio
    mass_servos = servos
    mass_margin = margin


    weight_fr = (
        mass_wing
        + mass_h_stab
        + mass_v_stab
        + mass_boom
        + mass_battery
        + mass_motor
        + mass_radio
        + mass_servos
        + mass_margin
    )


    # ========================================================
    # COMPONENT CG LOCATIONS
    # ========================================================

    loc_wing = c / 2

    loc_h_stab = (
        H_loc
        + c_h / 2
    )

    loc_v_stab = (
        H_loc
        + c_v / 2
    )

    loc_boom = (
        H_loc
        - motor_loc
    ) / 2

    loc_battery = batt_loc

    loc_motor = motor_loc

    loc_radio = 0

    loc_servos = H_loc / 2

    loc_margin = c / 2


    # ========================================================
    # MASS MOMENT
    # ========================================================

    cumsum_weight = (
        mass_wing * loc_wing
        + mass_h_stab * loc_h_stab
        + mass_v_stab * loc_v_stab
        + mass_boom * loc_boom
        + mass_battery * loc_battery
        + mass_motor * loc_motor
        + mass_radio * loc_radio
        + mass_servos * loc_servos
        + mass_margin * loc_margin
    )


    COM_fr = (
        cumsum_weight
        / weight
    )


    add_equality(
        "Center of mass calculation",
        COM - COM_fr,
        "Reported center of mass must match the mass-weighted component center of mass.",
    )


    add_equality(
        "Aircraft mass calculation",
        weight - weight_fr,
        "Aircraft mass must equal the sum of all component masses.",
    )


    # ========================================================
    # MANEUVER LOAD
    # ========================================================

    radius_turn = 10

    g = 9.81


    N = ca.sqrt(
        V ** 4
        / (radius_turn * g) ** 2
        + 1
    )


    add_equality(
        "Maneuver lift balance",
        L_h
        + L
        - weight * 9.8 * N,
        "Main wing lift plus tail lift must equal the required maneuver load.",
    )


    # ========================================================
    # STRUCTURAL DEFLECTION
    # ========================================================

    main_deflection = max_deflection(
        N * weight * 9.81,
        AR,
        S,
        E_foam,
        tau=0.12,
    )


    tail_deflection = max_deflection(
        N * weight * 9.81,
        AR_h,
        S_h,
        E,
        I_formula=I_formula,
        tau=0.002,
    )


    add_inequality(
        "Main wing deflection",
        0.08 * b - main_deflection,
        "Main wing deflection must be less than 8% of the wing half-span.",
    )


    add_inequality(
        "Horizontal tail deflection",
        0.1 * b_h - tail_deflection,
        "Horizontal tail deflection must be less than 10% of the horizontal tail half-span.",
    )


    # ========================================================
    # TAIL LOCATION
    # ========================================================

    add_inequality(
        "Tail location",
        H_loc - c,
        "Horizontal tail location must be behind the main wing chord.",
    )


    # ========================================================
    # BOOM TORSION
    # ========================================================

    J_boom = (
        0.141
        * boom_height ** 4
    )


    CL_v_max = 1.0


    L_v_max = (
        0.5
        * rho
        * V ** 2
        * S_v
        * CL_v_max
    )


    torque_boom = (
        L_v_max
        * (b_v / 2)
    )


    twist_angle_rad = (
        torque_boom
        * H_loc
        / (G_boom * J_boom)
    )


    max_twist_deg = 3

    max_twist_rad = (
        max_twist_deg
        * (pi / 180)
    )


    add_inequality(
        "Boom torsional deflection",
        max_twist_rad - twist_angle_rad,
        "Boom twist must be less than 3 degrees.",
    )


    # ========================================================
    # PROPULSION
    # ========================================================

    ct0 = 0.0282

    ct1 = -0.0573

    ct2 = -0.2022


    Tmax_static = 2

    Rprop = 0.1016

    Aprop = (
        np.pi
        * Rprop ** 2
    )


    Omega = ca.sqrt(
        Tmax_static
        / (
            0.5
            * rho
            * Rprop ** 2
            * Aprop
            * ct0
        )
    )


    Lambda = (
        V
        / (Omega * Rprop)
    )


    CT = (
        ct0
        + ct1 * Lambda
        + ct2 * Lambda ** 2
    )


    Tmax = (
        CT
        * 0.5
        * rho
        * (Omega * Rprop) ** 2
        * Aprop
    )


    add_inequality(
        "Available thrust",
        Tmax - D,
        "Available propulsive thrust must exceed aerodynamic drag.",
    )


    # ========================================================
    # OBJECTIVE
    # ========================================================

    opti.maximize(V)


    # ========================================================
    # SOLVE
    # ========================================================

    solve_error = None

    try:

        sol = opti.solve(
            behavior_on_failure="return_last",
            max_iter=10000,
        )

        stats = sol.stats()

        solver_success = bool(
            stats.get("success", False)
        )

        return_status = stats.get(
            "return_status",
            "Unknown",
        )

    except Exception as error:

        solver_success = False

        solve_error = str(error)

        stats = {}

        return_status = "Solver exception"

        sol = None


    # ========================================================
    # CONSTRAINT REPORT
    # ========================================================

    report = make_constraint_report(
        opti,
        constraints,
    )


    # ========================================================
    # SUCCESS CONDITION
    #
    # We require BOTH:
    #
    # 1. Solver says it succeeded
    # 2. Our explicit constraint checker says feasible
    # ========================================================

    success = (
        solver_success
        and report["feasible"]
    )


    # ========================================================
    # IF THE SOLVER FAILED
    # ========================================================

    if not success:

        try:

            opti.debug.show_infeasibilities()

        except Exception:
            pass


    # ========================================================
    # VALUE HELPER
    # ========================================================

    def value(expression):

        try:

            if sol is not None:
                return float(
                    sol.value(expression)
                )

        except Exception:
            pass


        try:

            return float(
                opti.debug.value(expression)
            )

        except Exception:

            return None


    # ========================================================
    # RETURN BASE RESULT
    # ========================================================

    result = {

        "success": success,

        "status": (
            "optimal"
            if success
            else "infeasible"
        ),

        "solver_status": return_status,

        "solver_error": solve_error,

        "constraints": {
            "feasible": report["feasible"],
            "n_violated": report["n_violated"],
            "n_satisfied": report["n_satisfied"],
            "violations": report["violations"],
            "satisfied": report["satisfied"],
        },

        "wing": {
            "S": float(S),
            "AR": float(AR),
            "span": value(b_total),
            "chord": value(c),
            "dihedral": float(dihedral),
            "deflection": value(main_deflection),
        },

        "horizontal_tail": {
            "S": value(S_h),
            "AR": value(AR_h),
            "span": value(b_h * 2),
            "chord": value(c_h),
            "x": value(H_loc),
            "deflection": value(tail_deflection),
        },

        "vertical_tail": {
            "S": value(S_v),
            "AR": value(AR_v),
            "span": value(b_v),
            "chord": value(c_v),
            "x": value(H_loc),
        },

        "performance": {
            "mass": value(weight),
            "velocity": value(V),
            "alpha": value(alpha),
            "CL": value(CL),
            "CL_h": value(CL_h),
            "drag": value(D),
            "lift": value(L),
            "tail_lift": value(L_h),
            "CD": value(CD),
            "CDi": value(CDi),
            "CD0": value(CD0),
            "cd_2d": value(cd_2d),
            "thrust": value(Tmax),
            "L_over_D": value(L_over_D),
            "load_factor": value(N),
            "tail_angle": value(i),
        },

        "stability": {
            "COM": value(COM),
            "neutral_point": value(npt),
            "static_margin": value(
                (npt - COM) / c
            ),
            "horizontal_volume": value(
                hor_vol_coef
            ),
            "vertical_volume": value(
                ver_vol_coef
            ),
            "spiral": value(spiral),
            "Cn_delta_r": value(
                Cn_delta_r
            ),
        },

        "locations": {
            "battery": value(batt_loc),
            "motor": value(motor_loc),
        },

        "mass": {
            "wing": value(mass_wing),
            "horizontal_tail": value(mass_h_stab),
            "vertical_tail": value(mass_v_stab),
            "boom": value(mass_boom),
            "battery": float(battery_mass),
            "motor": float(motor_mass),
            "radio": float(radio),
            "servos": float(servos),
            "margin": float(margin),
        },

        "structural": {
            "main_wing_deflection": value(
                main_deflection
            ),
            "main_wing_deflection_limit": value(
                0.08 * b
            ),
            "horizontal_tail_deflection": value(
                tail_deflection
            ),
            "horizontal_tail_deflection_limit": value(
                0.1 * b_h
            ),
            "boom_twist": value(
                twist_angle_rad
            ),
            "boom_twist_limit": float(
                max_twist_rad
            ),
        },
    }


    return result