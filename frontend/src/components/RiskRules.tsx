/** Collapsible reference of the rules the backend applies. */
export default function RiskRules() {
  return (
    <details className="rules">
      <summary>How risk is calculated</summary>
      <table>
        <thead>
          <tr>
            <th />
            <th>Low</th>
            <th>Moderate</th>
            <th>High</th>
            <th>Severe</th>
            <th>No Travel</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>Wind mph</th>
            <td>&lt;25</td>
            <td>25–34</td>
            <td>35–44</td>
            <td>45–54</td>
            <td>≥55</td>
          </tr>
          <tr>
            <th>Rain in/hr</th>
            <td>&lt;0.10</td>
            <td>0.10–0.25</td>
            <td>0.25–0.50</td>
            <td>0.50–1.00</td>
            <td>&gt;1.00</td>
          </tr>
          <tr>
            <th>Snow in/hr</th>
            <td>&lt;0.5</td>
            <td>0.5–1.0</td>
            <td>1.0–2.0</td>
            <td>2.0–3.0</td>
            <td>&gt;3.0</td>
          </tr>
        </tbody>
      </table>
      <ul>
        <li>Load: 45–54 mph with &gt;30,000 lb is No Travel; 35–44 mph with &gt;40,000 lb is Severe.</li>
        <li>A checkpoint takes the worst of wind, rain and snow. Shared band edges go to the higher band.</li>
        <li>Each checkpoint covers the road halfway to its neighbours, so every mile is counted once.</li>
        <li>
          Ranking: fewest No Travel miles, then Severe miles, High miles, mile-weighted average risk (Low 0 … No
          Travel 4), and finally travel time.
        </li>
      </ul>
    </details>
  )
}
