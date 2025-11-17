import LineChartOne, { type LineSeries } from "@/components/charts/line/LineChartOne";
import ComponentCard from "@/components/common/ComponentCard";
import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "Next.js Line Chart | TailAdmin - Next.js Dashboard Template",
  description:
    "This is Next.js Line Chart page for TailAdmin - Next.js Tailwind CSS Admin Dashboard Template",
};

const sampleSeries: LineSeries[] = [
  {
    name: "Sample Data",
    data: [
      { x: new Date("2024-01-01").getTime(), y: 30 },
      { x: new Date("2024-01-02").getTime(), y: 40 },
      { x: new Date("2024-01-03").getTime(), y: 35 },
      { x: new Date("2024-01-04").getTime(), y: 50 },
      { x: new Date("2024-01-05").getTime(), y: 45 },
    ],
  },
];

export default function LineChart() {
  return (
    <div>
      <PageBreadcrumb pageTitle="Line Chart" />
      <div className="space-y-6">
        <ComponentCard title="Line Chart 1">
          <LineChartOne series={sampleSeries} />
        </ComponentCard>
      </div>
    </div>
  );
}
