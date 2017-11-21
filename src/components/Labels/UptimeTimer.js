/* eslint-disable no-nested-ternary */

import React, { Component } from 'react';
import PropTypes from 'prop-types';
import moment from 'moment';
import { ArrowUp, Clock } from 'react-feather';

import './UptimeTimer.css';

const propTypes = {
  startTime: PropTypes.number.isRequired
};

class Timer extends Component {
  constructor(props) {
    super(props);
    this.state = {
      intervalTimer: null,
      internalStartTime: props.startTime,
      time: null
    };

    this.onUpdate = prevProps => {
      if (prevProps.startTime) {
        if (!this.state.intervalTimer) {
          if (this.props.startTime) {
            const intervalTimer = setInterval(() => this.tickTime(), 1000);
            this.setState({ intervalTimer });
            this.tickTime();
          }
        }
        if (this.props.startTime !== this.state.internalStartTime) {
          setTimeout(() => {
            this.setState({ internalStartTime: this.props.startTime });
          }, 1800);
        }
      } else if (this.props.startTime) {
        const intervalTimer = setInterval(() => this.tickTime(), 1000);
        this.setState({
          intervalTimer,
          internalStartTime: this.props.startTime
        });
        this.tickTime();
      }
    };

    this.tickTime = () => {
      const now = moment();
      const startTime = moment(this.state.internalStartTime);
      const diff = moment.duration(now.diff(startTime));
      let hours = diff.hours();
      hours = hours >= 0 ? (hours < 10 ? `0${hours}` : hours) : '00';
      let minutes = diff.minutes();
      minutes = minutes >= 0 ? (minutes < 10 ? `0${minutes}` : minutes) : '00';
      let seconds = diff.seconds();
      seconds = seconds >= 0 ? (seconds < 10 ? `0${seconds}` : seconds) : '00';

      const time = `${hours}:${minutes}:${seconds}`;
      this.setState({ time });
    };
  }

  componentDidUpdate(prevProps) {
    this.onUpdate(prevProps);
  }

  componentWillUnmount() {
    clearInterval(this.state.intervalTimer);
  }

  render() {
    return (
      <div className="ut">
        <span className="ut-text">
          <ArrowUp color="#02fa7b" size={18} />
          <Clock color="#02fa7b" size={16} />
        </span>
        <span className="ut-timer">{this.state.time}</span>
      </div>
    );
  }
}

Timer.propTypes = propTypes;

export default Timer;
