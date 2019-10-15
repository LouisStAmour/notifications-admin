import React from "react";
import { getMinHour, getMaxHour } from "./dateUtils";

export const Hour = ({ amPM, hour, isToday, handleClick }) => {
  return (
    <div className="hour-choice">
      <input
        onChange={e => {
          const hour = e.target.value;
          handleClick(hour);
        }}
        value={hour}
        name="hour"
        style={{ width: 50 }}
        type="number"
        min={getMinHour({ amPM: amPM, isToday: isToday })}
        max={getMaxHour()}
        aria-label="Hour to send"
        className="form-control form-control-1-1 "
      />
      <label htmlFor="hour">O'Clock</label>
    </div>
  );
};