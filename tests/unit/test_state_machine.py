import unittest

from core.conversation import ConversationContext, CoreState, CoreStateMachine, EventBus, InvalidStateTransition


class StateMachineTests(unittest.TestCase):
    def test_normal_typed_round_trip_emits_state_changes(self) -> None:
        context = ConversationContext("conv", "user")
        bus = EventBus()
        state = CoreStateMachine(context, bus, initial_state=CoreState.LISTENING)
        state.transition(CoreState.THINKING)
        state.transition(CoreState.SPEAKING)
        state.transition(CoreState.LISTENING)
        self.assertEqual(state.state, CoreState.LISTENING)
        self.assertEqual(sum(e.event_type == "core.state.changed" for e in bus.history), 3)

    def test_invalid_transition_is_rejected_without_mutating_state(self) -> None:
        context = ConversationContext("conv", "user")
        state = CoreStateMachine(context, EventBus(), initial_state=CoreState.SLEEPING)
        with self.assertRaises(InvalidStateTransition):
            state.transition(CoreState.SPEAKING)
        self.assertEqual(state.state, CoreState.SLEEPING)


if __name__ == "__main__":
    unittest.main()
