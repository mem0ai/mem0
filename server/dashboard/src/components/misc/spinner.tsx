import React from "react";

export function Spinner({ size = "small", className = "" }) {
  const spinnerSize = size === "small" ? "w-4 h-4" : "w-6 h-6";
  return (
    <div
      className={`${spinnerSize} ${className} animate-spin rounded-full border-y-2 border-memBorder-primary`}
    ></div>
  );
}
