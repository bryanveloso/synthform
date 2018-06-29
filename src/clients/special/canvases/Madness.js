import React from 'react';

import styled from 'styled-components';

import * as Providers from 'providers';
import {
  Progression,
  MadnessNotifier as Notifier
} from 'clients/special/components';

const propTypes = {};

const Madness = () => (
  <Wrapper>
    <Providers.Madness>
      {(state, notifierPool, onComplete) => (
        <Container>
          <StyledProgression payload={state.bits} />
          <StyledNotifier notifierPool={notifierPool} onComplete={onComplete} />
        </Container>
      )}
    </Providers.Madness>
  </Wrapper>
);

Madness.propTypes = propTypes;

const Wrapper = styled.div`
  width: 480px;
  height: 100vh;
`;

const StyledProgression = styled(Progression)`
  margin: 0 auto;
`;

const StyledNotifier = styled(Notifier)`
  margin: -56px auto 0;
`;

const Container = styled.div``;

export default Madness;