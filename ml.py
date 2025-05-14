import datetime

class Task:
    def __init__(self, name, priority, duration, energy, deadline):
        self.name = name
        self.priority = int(priority)
        self.duration = int(duration)  # in minutes
        self.energy = int(energy)
        self.deadline = datetime.datetime.strptime(deadline, "%Y-%m-%d")

    def __repr__(self):
        return f"{self.name} (Priority: {self.priority}, Duration: {self.duration} mins, Deadline: {self.deadline.date()})"


def find_free_slots(events, start_time, end_time):
    slots = []
    busy = []

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        busy.append((datetime.datetime.fromisoformat(start), datetime.datetime.fromisoformat(end)))

    busy.sort()
    current = start_time

    for start, end in busy:
        if current < start:
            slots.append((current, start))
        current = max(current, end)

    if current < end_time:
        slots.append((current, end_time))

    return slots


def assign_tasks_to_slots(tasks, free_slots):
    tasks.sort(key=lambda t: (-t.priority, t.deadline))
    scheduled = []

    for task in tasks:
        for i, (slot_start, slot_end) in enumerate(free_slots):
            slot_length = int((slot_end - slot_start).total_seconds() // 60)

            if slot_length >= task.duration:
                scheduled_time = slot_start.strftime("%H:%M") + " - " + (slot_start + datetime.timedelta(minutes=task.duration)).strftime("%H:%M")
                scheduled.append(f"{scheduled_time}: {task.name} [Priority {task.priority}]")
                # Update slot
                new_start = slot_start + datetime.timedelta(minutes=task.duration)
                free_slots[i] = (new_start, slot_end)
                break

    return scheduled


# ✅ ADD THIS FUNCTION TO FIX YOUR IMPORT ERROR
def optimize_tasks(task_dicts, calendar_events):
    tasks = [Task(**task) for task in task_dicts]
    now = datetime.datetime.now()
    end_of_day = now.replace(hour=23, minute=59, second=59)
    free_slots = find_free_slots(calendar_events, now, end_of_day)
    return assign_tasks_to_slots(tasks, free_slots)
