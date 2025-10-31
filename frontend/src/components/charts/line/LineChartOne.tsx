"use client";
import React from "react";
import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";

const ReactApexChart = dynamic(() => import("react-apexcharts"), { ssr: false });

export type LinePoint = { x: number | string; y: number }; // x = ms epoch or ISO
export type LineSeries = { name: string; data: LinePoint[] };

export default function LineChartOne({
  series,
  height = 310,
  title,
}: {
  series: LineSeries[];
  height?: number;
  title?: string;
}) {
  const options: ApexOptions = {
    chart: { type: "line", height, toolbar: { show: false }, fontFamily: "Outfit, sans-serif" },
    stroke: { curve: "straight", width: 2 },
    xaxis: {
      type: "datetime",
      labels: { datetimeUTC: false },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: { style: { fontSize: "12px", colors: ["#6B7280"] } },
    },
    dataLabels: { enabled: false },
    tooltip: {
      x: { format: "yyyy-MM-dd HH:mm" },
    },
    grid: { yaxis: { lines: { show: true } }, xaxis: { lines: { show: false } } },
    legend: { show: !!title, position: "top", horizontalAlign: "left" },
    colors: ["#465FFF"],
    title: title ? { text: title, style: { fontWeight: 600 } } : undefined,
  };

  return (
    <div className="max-w-full overflow-x-auto custom-scrollbar">
      <div className="min-w-[600px]">
        <ReactApexChart options={options} series={series} type="line" height={height} />
      </div>
    </div>
  );
}
