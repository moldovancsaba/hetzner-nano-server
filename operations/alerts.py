"""Debounced alert and recovery state, with no recurring healthy notifications."""
def advance(previous, observed, now):
    state = dict(previous or {})
    active = dict(state.get('active_alerts', {}))
    pending = dict(state.get('pending', {}))
    changes = list(state.get('changes', []))
    revision = state.get('revision',0)
    for code in set(pending)|set(active)|set(observed):
        present = code in observed
        old = pending.get(code, {})
        count = old.get('count',0)+1 if old.get('present') is present else 1
        pending[code] = {'present':present,'count':count}
        # Debounce: a change (alert present or cleared) is acted on only after 3 consecutive samples agree.
        if count < 3:
            continue
        if present and code not in active:
            revision += 1
            active[code] = {**observed[code],'first_seen_at':now}
            changes.append({'revision':revision,'at':now,'state':'alert','code':code,**observed[code]})
        elif not present and code in active:
            revision += 1
            changes.append({'revision':revision,'at':now,'state':'recovered','code':code,'severity':'info','message':'Recovered: '+active[code]['message']})
            del active[code]
            del pending[code]
        elif not present and code not in active:
            pending.pop(code,None)
    return {'schema_version':'operational-monitor.v1','checked_at':now,'revision':revision,
            'active_alerts':active,'pending':pending,'changes':changes[-100:]}
