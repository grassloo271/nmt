import { useState } from "react";
import "./App.css";
import { lookupAircraft } from "./lookupTable";


type Violation = {
  name: string;
  type: string;
  actual_residual: number;
  violation: number;
  description: string;
};

type AircraftResult = {
  success: boolean;
  status: string;
  solver_status?: string;
  solver_error?: string | null;

  constraints?: {
    feasible: boolean;
    n_violated: number;
    n_satisfied: number;
    violations: Violation[];
  };

  wing?: {
    S: number;
    AR: number;
    span: number;
    chord: number;
    dihedral: number;
    deflection: number;
  };

  horizontal_tail?: {
    S: number;
    AR: number;
    span: number;
    chord: number;
    x: number;
    deflection: number;
  };

  vertical_tail?: {
    S: number;
    AR: number;
    span: number;
    chord: number;
    x: number;
  };

  performance?: {
    mass: number;
    velocity: number;
    alpha: number;
    CL: number;
    CL_h: number;
    drag: number;
    lift: number;
    tail_lift: number;
    CD: number;
    CDi: number;
    CD0: number;
    cd_2d: number;
    thrust: number;
    L_over_D: number;
    load_factor: number;
    tail_angle: number;
  };

  stability?: {
    COM: number;
    neutral_point: number;
    static_margin: number;
    horizontal_volume: number;
    vertical_volume: number;
    spiral: number;
    Cn_delta_r: number;
  };

  locations?: {
    battery: number;
    motor: number;
  };

  mass?: {
    wing: number;
    horizontal_tail: number;
    vertical_tail: number;
    boom: number;
    battery: number;
    motor: number;
    radio: number;
    servos: number;
    margin: number;
  };

  structural?: {
    main_wing_deflection: number;
    main_wing_deflection_limit: number;
    horizontal_tail_deflection: number;
    horizontal_tail_deflection_limit: number;
    boom_twist: number;
    boom_twist_limit: number;
  };
};


// ============================================================
// HELPERS
// ============================================================

function fmt(
  value: number | undefined,
  digits = 3
) {
  if (
    value === undefined ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return value.toFixed(digits);
}


// ============================================================
// AIRCRAFT DRAWING
// ============================================================

function AircraftView({
  result,
}: {
  result: AircraftResult | null;
}) {
  const wingSpan =
    result?.wing?.span ?? 2;

  const motorLoc =
    result?.locations?.motor ?? 0.1;

  const horChord =
    result?.horizontal_tail?.chord ?? 0.06;

  const vertSpan =
    result?.vertical_tail?.span ?? 0.06;

  const xloc =
    result?.horizontal_tail?.x ?? 0.9;

  const wingChord =
    result?.wing?.chord ?? 0.25;

  const tailSpan =
    result?.horizontal_tail?.span ?? 0.7;

  /*
   * Normalize the geometry so that the aircraft always
   * fits nicely inside the drawing area.
   */

  const scale = Math.min(
    260 / wingSpan,
    150 / Math.max(wingChord, 0.1)
  );

  const mainWingWidth =
    Math.max(160, wingSpan * scale);

  const distToTail =
    Math.max(160, xloc * scale);

  const horizontalChord = 
    Math.min(100, horChord * scale);

  const motorLocation = 
    Math.min(-50, motorLoc * scale);

  const mainWingDepth =
    Math.max(20, wingChord * scale);

  const tailWidth =
    Math.max(55, tailSpan * scale);

  const vertSpanWidth =
    Math.max(55, vertSpan * scale);

  return (
    
    <div className="aircraft-view">

  <div className="view-label">
    SIDE VIEW
  </div>

  <svg
    viewBox="0 0 700 420"
    className="aircraft-svg"
  >

    {/* Fuselage — nose points LEFT */}
    <path
      d={`
        M ${300 + motorLocation} 215
        L ${300 + distToTail} 215
        L ${300 + distToTail} 205
        L ${300 + motorLocation} 205
        Z
      `}
      className="fuselage"
    />

    

    {/* Main wing — extends UP/DOWN */}
    <path
      d={`
        M ${300 - mainWingWidth * 0.5 / 2} ${210 - mainWingWidth * 0.866 / 2}
        L ${300 + mainWingDepth -  mainWingWidth * 0.5 / 2} ${210 - mainWingWidth * 0.866 / 2 }
        L ${300 + mainWingDepth +  mainWingWidth * 0.5 / 2} ${210 + mainWingWidth * 0.866 / 2}
        L ${300 +  mainWingWidth * 0.5 / 2} ${210 + mainWingWidth * 0.866 / 2}
        Z
      `}
      className="main-wing"
    />

    {/* Horizontal tail — near the REAR */}
    <path
      d={`
        M ${distToTail + 300 - tailWidth / 4 } ${210 - tailWidth / 2 * 0.866}
        L ${distToTail + 300 + horizontalChord - tailWidth / 4 } ${210 - tailWidth / 2 * 0.866}
        L ${distToTail + 300 + horizontalChord + tailWidth / 4 } ${210 + tailWidth / 2 * 0.866}
        L ${distToTail + 300 + tailWidth / 4 } ${210 + tailWidth / 2 * 0.866}
        Z
      `}
      className="tail"
    />

    {/* Vertical stabilizer */}
    <path
      d={`
        M ${distToTail + 300  +  vertSpanWidth/2} ${210 - vertSpanWidth}
        L ${distToTail + 300 + horizontalChord +  vertSpanWidth/2 } ${210  - vertSpanWidth }
        L ${distToTail + 300 + horizontalChord } ${210}
        L ${distToTail + 300  } ${210 }
        Z
      `}
      className="vertical-tail"
    />

  </svg>


      <div className="aircraft-dimensions">

        <div>
          <span>Span</span>
          <strong>
            {fmt(result?.wing?.span)} m
          </strong>
        </div>

        <div>
          <span>Chord</span>
          <strong>
            {fmt(result?.wing?.chord)} m
          </strong>
        </div>

        <div>
          <span>Tail span</span>
          <strong>
            {fmt(result?.horizontal_tail?.span)} m
          </strong>
        </div>

      </div>

    </div>
  );
}


// ============================================================
// RESULT ITEM
// ============================================================

function Metric({
  label,
  value,
  unit,
}: {
  label: string;
  value: number | undefined;
  unit?: string;
}) {
  return (
    <div className="metric">

      <span className="metric-label">
        {label}
      </span>

      <span className="metric-value">
        {fmt(value)}
        {unit && (
          <small> {unit}</small>
        )}
      </span>

    </div>
  );
}


// ============================================================
// BUILD SPEC HELPERS
// ============================================================

function totalMass(mass: AircraftResult["mass"]) {
  if (!mass) return undefined;

  return (
    mass.wing +
    mass.horizontal_tail +
    mass.vertical_tail +
    mass.boom +
    mass.battery +
    mass.motor +
    mass.radio +
    mass.servos +
    mass.margin
  );
}

function SpecRow({
  label,
  value,
  unit,
}: {
  label: string;
  value: number | undefined;
  unit?: string;
}) {
  return (
    <div className="spec-row">
      <span>{label}</span>
      <strong>
        {fmt(value)}
        {unit && <small> {unit}</small>}
      </strong>
    </div>
  );
}


// ============================================================
// APP
// ============================================================

function App() {

  const [S, setS] = useState(0.15);
  const [AR, setAR] = useState(5);
  const [margin, setMargin] = useState(0.03);

  const [result, setResult] =
    useState<AircraftResult | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  // ==========================================================
  // OPTIMIZE
  // ==========================================================

  
 
 async function optimize() {
    setLoading(true);
    setError(null);

    try {
      const data = lookupAircraft(S, AR, margin);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to compute result."
      );
    } finally {
      setLoading(false);
    }
  }


  return (
    <div className="app">

      {/* ======================================================
          HEADER
      ====================================================== */}

      <header className="topbar">

        <div>
          <div className="eyebrow">
            AIRCRAFT DESIGN
          </div>

          <h1>
            Glider Design Explorer
          </h1>
        </div>

        <div className="topbar-right">
          S / AR OPTIMIZATION
        </div>

      </header>


      {/* ======================================================
          MAIN
      ====================================================== */}

      <main className="layout">


        {/* ====================================================
            LEFT CONTROL PANEL
        ==================================================== */}

        <aside className="controls-panel">

          <div className="section-label">
            DESIGN INPUTS
          </div>


          {/* Wing area */}

          <div className="control">

            <div className="control-heading">

              <span>
                Wing area
              </span>

              <strong>
                {S.toFixed(2)}
                <small> m²</small>
              </strong>

            </div>

            <input
              type="range"
              min="0.1"
              max="0.2"
              step="0.005"
              value={S}
              onChange={(e) =>
                setS(
                  Number(e.target.value)
                )
              }
            />

            <div className="range-labels">
              <span>0.1</span>
              <span>0.2</span>
            </div>

          </div>


          {/* Aspect ratio */}

          <div className="control">

            <div className="control-heading">

              <span>
                Aspect ratio
              </span>

              <strong>
                {AR.toFixed(1)}
              </strong>

            </div>

            <input
              type="range"
              min="4"
              max="8"
              step="0.1"
              value={AR}
              onChange={(e) =>
                setAR(
                  Number(e.target.value)
                )
              }
            />

            <div className="range-labels">
              <span>4</span>
              <span>8</span>
            </div>

          </div>

          {/* Aspect ratio */}

          <div className="Extra Mass">

            <div className="control-heading">

              <span>
                Extra Mass
              </span>

              <strong>
                {margin.toFixed(3)}
                <small> kg</small>
              </strong>

            </div>

            <input
              type="range"
              min="0.02"
              max="0.1"
              step="0.005"
              value={margin}
              onChange={(e) =>
                setMargin(
                  Number(e.target.value)
                )
              }
            />

            <div className="range-labels">
              <span>0.02</span>
              <span>0.1</span>
            </div>

          </div>

          <button
            className="optimize-button"
            onClick={optimize}
            disabled={loading}
          >

            <span>
              {loading
                ? "OPTIMIZING..."
                : "OPTIMIZE AIRCRAFT"}
            </span>

            {!loading && (
              <span className="button-arrow">
                →
              </span>
            )}

          </button>


          {error && (
            <div className="error">
              {error}
            </div>
          )}


          {/* Input summary */}

          <div className="input-summary">

            <div>
              <span>Area</span>
              <strong>{S.toFixed(2)} m²</strong>
            </div>

            <div>
              <span>Aspect ratio</span>
              <strong>{AR.toFixed(1)}</strong>
            </div>

          </div>

        </aside>


        {/* ====================================================
            CENTER AIRCRAFT
        ==================================================== */}

        <section className="aircraft-panel">

          <div className="section-label">
            GEOMETRY
          </div>

          <AircraftView
            result={result}
          />

          <div className="aircraft-caption">

            <div>
              <span className="legend-dot wing-dot" />
              Main wing
            </div>

            <div>
              <span className="legend-dot tail-dot" />
              Tail
            </div>

            <div>
              <span className="legend-dot cg-dot" />
              CG
            </div>

          </div>

        </section>


        {/* ====================================================
            RIGHT RESULTS
        ==================================================== */}

        <aside className="results-panel">


          {/* ==================================================
    CONSTRAINTS
================================================== */}

<section className="result-section">

  <div className="section-header">

    <div>
      <div className="section-label">
        DESIGN STATUS
      </div>

      <h2>
        Constraints
      </h2>
    </div>

    {result && (
      <div
        className={
          result.constraints &&
          result.constraints.n_violated === 0
            ? "status feasible"
            : "status infeasible"
        }
      >
        {result.constraints &&
        result.constraints.n_violated === 0
          ? "FEASIBLE"
          : "INFEASIBLE"}
      </div>
    )}

  </div>


  {/* Nothing has been run yet */}

  {!result && (
    <div className="empty-state">
      Run the optimizer to evaluate the design.
    </div>
  )}


  {/* ==================================================
      VIOLATIONS
  ================================================== */}

  {result &&
    result.constraints &&
    result.constraints.violations &&
    result.constraints.violations.length > 0 && (

      <div className="violations">

        <div className="violation-count">

          {result.constraints.violations.length}
          {" "}
          constraint
          {result.constraints.violations.length === 1
            ? ""
            : "s"}
          {" "}violated

        </div>


        {result.constraints.violations.map(
          (violation, index) => (

            <div
              className="violation"
              key={`${violation.name}-${index}`}
            >

              <div className="violation-heading">

                <span className="warning">
                  !
                </span>

                <strong>
                  {violation.name}
                </strong>

              </div>


              <p>
                {violation.description}
              </p>


              <div className="violation-number">

                <span>
                  Residual
                </span>

                <strong>
                  {violation.actual_residual.toFixed(5)}
                </strong>

              </div>


              <div className="violation-number">

                <span>
                  Amount violated
                </span>

                <strong>
                  {violation.violation.toFixed(5)}
                </strong>

              </div>

            </div>

          )
        )}

      </div>
    )}


  {/* ==================================================
      NO VIOLATIONS
  ================================================== */}

  {result &&
    result.constraints &&
    result.constraints.violations &&
    result.constraints.violations.length === 0 && (

      <div className="all-good">

        <span className="check">
          ✓
        </span>

        <div>

          <strong>
            All constraints satisfied
          </strong>

          <span>
            This configuration is feasible.
          </span>

        </div>

      </div>

    )}

</section>


          {/* ==================================================
              PERFORMANCE
          ================================================== */}

          {result?.performance && (

            <section className="result-section">

              <div className="section-label">
                PERFORMANCE
              </div>

              <div className="metrics">

                <Metric
                  label="Velocity"
                  value={result.performance.velocity}
                  unit="m/s"
                />

                <Metric
                  label="L / D"
                  value={result.performance.L_over_D}
                />

                <Metric
                  label="Mass"
                  value={result.performance.mass}
                  unit="kg"
                />

                <Metric
                  label="Thrust"
                  value={result.performance.thrust}
                  unit="N"
                />

                <Metric
                  label="Drag"
                  value={result.performance.drag}
                  unit="N"
                />

                <Metric
                  label="Load factor"
                  value={result.performance.load_factor}
                />

              </div>

            </section>

          )}


         

        </aside>

      </main>


      {/* ======================================================
          BUILD SPEC ADDENDUM

          Everything needed to physically assemble the aircraft:
          where each component sits, its dimensions, and its
          mass.
      ====================================================== */}

      {result && result.success && (

        <section className="build-specs">

          <div className="section-label">
            BUILD SPECIFICATIONS
          </div>

          <h2>Physical Assembly Reference</h2>

          <div className="build-specs-grid">

            {/* ================================================
                COMPONENT LOCATIONS & DIMENSIONS
            ================================================ */}

            <div className="spec-card">

              <h3>Main Wing</h3>

              <SpecRow
                label="Position (from nose)"
                value={0}
                unit="m"
              />
              <SpecRow
                label="Span (full)"
                value={result.wing?.span}
                unit="m"
              />
              <SpecRow
                label="Chord"
                value={result.wing?.chord}
                unit="m"
              />
              <SpecRow
                label="Area"
                value={result.wing?.S}
                unit="m²"
              />
              <SpecRow
                label="Aspect ratio"
                value={result.wing?.AR}
              />
              <SpecRow
                label="Dihedral"
                value={result.wing?.dihedral}
                unit="deg"
              />

            </div>

            <div className="spec-card">

              <h3>Horizontal Tail</h3>

              <SpecRow
                label="Position (from wing LE)"
                value={result.horizontal_tail?.x}
                unit="m"
              />
              <SpecRow
                label="Span (full)"
                value={result.horizontal_tail?.span}
                unit="m"
              />
              <SpecRow
                label="Chord"
                value={result.horizontal_tail?.chord}
                unit="m"
              />
              <SpecRow
                label="Area"
                value={result.horizontal_tail?.S}
                unit="m²"
              />
              <SpecRow
                label="Aspect ratio"
                value={result.horizontal_tail?.AR}
              />

            </div>

            <div className="spec-card">

              <h3>Vertical Tail</h3>

              <SpecRow
                label="Position (from wing LE)"
                value={result.vertical_tail?.x}
                unit="m"
              />
              <SpecRow
                label="Span"
                value={result.vertical_tail?.span}
                unit="m"
              />
              <SpecRow
                label="Chord"
                value={result.vertical_tail?.chord}
                unit="m"
              />
              <SpecRow
                label="Area"
                value={result.vertical_tail?.S}
                unit="m²"
              />
              <SpecRow
                label="Aspect ratio"
                value={result.vertical_tail?.AR}
              />

            </div>

            <div className="spec-card">

              <h3>Component Placement</h3>

              <SpecRow
                label="Battery position"
                value={result.locations?.battery}
                unit="m from nose"
              />
              <SpecRow
                label="Motor position"
                value={result.locations?.motor}
                unit="m from nose"
              />
              <SpecRow
                label="Center of mass (COM)"
                value={result.stability?.COM}
                unit="m from nose"
              />
              <SpecRow
                label="Neutral point"
                value={result.stability?.neutral_point}
                unit="m from nose"
              />
              <SpecRow
                label="Static margin"
                value={result.stability?.static_margin}
              />

            </div>


            {/* ================================================
                MASS BREAKDOWN
            ================================================ */}

            <div className="spec-card">

              <h3>Mass Breakdown</h3>

              <SpecRow
                label="Main wing"
                value={result.mass?.wing}
                unit="kg"
              />
              <SpecRow
                label="Horizontal tail"
                value={result.mass?.horizontal_tail}
                unit="kg"
              />
              <SpecRow
                label="Vertical tail"
                value={result.mass?.vertical_tail}
                unit="kg"
              />
              <SpecRow
                label="Boom"
                value={result.mass?.boom}
                unit="kg"
              />
              <SpecRow
                label="Battery"
                value={result.mass?.battery}
                unit="kg"
              />
              <SpecRow
                label="Motor"
                value={result.mass?.motor}
                unit="kg"
              />
              <SpecRow
                label="Radio"
                value={result.mass?.radio}
                unit="kg"
              />
              <SpecRow
                label="Servos"
                value={result.mass?.servos}
                unit="kg"
              />
              <SpecRow
                label="Extra margin"
                value={result.mass?.margin}
                unit="kg"
              />

              <div className="spec-row spec-total">
                <span>Total mass</span>
                <strong>
                  {fmt(totalMass(result.mass))}
                  <small> kg</small>
                </strong>
              </div>

            </div>


            {/* ================================================
                STRUCTURAL LIMITS
            ================================================ */}

            <div className="spec-card">

              <h3>Structural Deflection</h3>

              <SpecRow
                label="Main wing deflection"
                value={result.structural?.main_wing_deflection}
                unit="m"
              />
              <SpecRow
                label="Main wing deflection limit"
                value={result.structural?.main_wing_deflection_limit}
                unit="m"
              />
              <SpecRow
                label="Tail deflection"
                value={result.structural?.horizontal_tail_deflection}
                unit="m"
              />
              <SpecRow
                label="Tail deflection limit"
                value={result.structural?.horizontal_tail_deflection_limit}
                unit="m"
              />
              <SpecRow
                label="Boom twist"
                value={result.structural?.boom_twist}
                unit="rad"
              />
              <SpecRow
                label="Boom twist limit"
                value={result.structural?.boom_twist_limit}
                unit="rad"
              />

            </div>

          </div>

        </section>

      )}

    </div>
  );
}

export default App;