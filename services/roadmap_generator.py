def generate_learning_roadmap(missing_skills):

    roadmap = []

    for skill in missing_skills:
        roadmap.append({
            "skill": skill,
            "course": f"Learn {skill} from beginner to advanced.",
            "priority": "High"
        })

    return roadmap


if __name__ == "__main__":

    skills = [
        "Docker",
        "TensorFlow",
        "Machine Learning"
    ]

    from pprint import pprint

    pprint(generate_learning_roadmap(skills))