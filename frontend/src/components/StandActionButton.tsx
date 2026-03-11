import React from "react";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
}

export const StandActionButton: React.FC<Props> = ({ label, ...rest }) => {
  return (
    <button className="btn btn-primary" {...rest}>
      {label}
    </button>
  );
};

