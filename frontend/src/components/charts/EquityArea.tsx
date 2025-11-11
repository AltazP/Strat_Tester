"use client";
import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";
const ReactApexChart = dynamic(() => import("react-apexcharts"), { ssr: false });

export default function EquityArea({ series, height=320 }: { series: {name:string; data:{x:number;y:number}[]}[]; height?: number; }) {
  const options: ApexOptions = {
    chart: { type: "area", height, toolbar: { show: false }, fontFamily: "Inter, ui-sans-serif" },
    stroke: { width: 2, curve: "straight" },
    dataLabels: { enabled: false },
    markers: { size: 0 },
    xaxis: { type: "datetime", labels: { datetimeUTC: false } },
    yaxis: {
      decimalsInFloat: 2,
      labels: { formatter: (v) => (Math.abs(v) < 1e-6 ? "0" : v.toFixed(2)) },
    },
    grid: { yaxis: { lines: { show: true } } },
    tooltip: { x: { format: "yyyy-MM-dd HH:mm" }, y: { formatter: (v) => v.toFixed(2) } },
    fill: { type: "gradient", gradient: { opacityFrom: 0.45, opacityTo: 0 } },
  };
  return <ReactApexChart options={options} series={series} type="area" height={height} />;
}
