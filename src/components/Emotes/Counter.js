import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import FlipMove from 'react-flip-move';
import { List } from 'immutable';

import { emoteFetch } from 'actions/emotes';
import * as selectors from 'selectors';

import CounterItem from './CounterItem';

import './Counter.css';

const propTypes = {
  emotes: PropTypes.instanceOf(List).isRequired,
  request: PropTypes.func.isRequired
};

class Counter extends Component {
  componentDidMount() {
    this.props.request();
  }

  render() {
    const { emotes } = this.props;
    return (
      <FlipMove typeName="ol" className="ec" easing="ease">
        {emotes.map(emoteData => (
          <CounterItem {...emoteData.toJS()} code={emoteData.get('key')} />
        ))}
      </FlipMove>
    );
  }
}

Counter.propTypes = propTypes;

function mapStateToProps(state) {
  return {
    emotes: selectors.getTotalEmoteCounts(state)
  };
}

function mapDispatchToProps(dispatch) {
  return bindActionCreators(
    {
      request: () => dispatch(emoteFetch.request())
    },
    dispatch
  );
}

export default connect(mapStateToProps, mapDispatchToProps)(Counter);