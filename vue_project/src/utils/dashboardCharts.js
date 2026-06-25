import * as echarts from 'echarts/core'
import { PieChart, ScatterChart } from 'echarts/charts'
import { GeoComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  PieChart,
  ScatterChart,
  GeoComponent,
  TooltipComponent,
  CanvasRenderer
])

export default echarts
