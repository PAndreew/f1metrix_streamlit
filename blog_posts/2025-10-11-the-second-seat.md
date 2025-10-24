The second seat at Red Bull Racing has long been considered the toughest drive in Formula 1. Paired with a generational talent like Max Verstappen, the pressure to perform is immense, and the team's patience is notoriously thin. The 2024-2025 season has been a perfect case study, with a revolving door that saw Sergio Pérez, Liam Lawson, and Yuki Tsunoda all take a turn.

This turmoil raises several critical questions from a performance perspective:
1.  **Was Red Bull justified in sacking Sergio Pérez after the 2024 season?**
2.  **Was the decision to replace the almost-rookie Liam Lawson after just two races a data-driven move or a knee-jerk reaction?**
2.  **Was Yuki Tsunoda the right replacement or should they instead promote F2 runner-up Isack Hadjar?**

Using data from our F1 performance model, let's analyze the drivers at the heart of this Red Bull trifle.

### The Foundational Numbers: A Look at Career Skill

Before diving into specific seasons, it's crucial to establish a baseline for each driver. The following chart displays our model's "Conservative Skill Estimate" (`u0_skill_lower_bound`) and "Mean Skill Estimate" (`u0_skill_mean`), which represents a driver's core talent level range, free of age, experience car and any other modifiers - their genius. Just a reminder: the average driver has an `u0_skill` of 0.0. I also included Verstappen as a reference.

<!-- PLOT:all_time_skill -->

Pérez, a seasoned veteran, has a proven track record of being... well being a bit above average driver with some glimpses of greatness. His heroics in 2021 Abu Dhabi will never be forgotten. Tsunoda on the other hand comes through as someone who barely scratches the requirements of being a Formula 1 driver. In fact the gap between Tsunoda and Perez is almost equal to the gap between Verstappen and Perez. We have low amount of data for Lawson and even more so for Hadjar, but based on what we have **BOTH** of them are more talented than Tsunoda. Hadjar's score reflects the model's cautious approach with rookies and his baseline will most likely increase for next year. Remember we're only talking about raw talent now, which does not always necessarily translate to better results due to other factors such as age, experience, yearly driver effects and most importantly - a bad car.

### Part A: Analyzing the Dismissal of Sergio Pérez

Sergio Pérez's 2024 season was a tale of inconsistency. While he secured 'some' points for the team, the performance gap to his teammate was often stark, maybe embarassing even. To determine if this was just a dip in form or a significant decline, we can track his "Yearly Pure Skill Score" over the past few seasons.

<!-- PLOT:yearly_skill_comparison -->

As you can see, Pérez's "Pure Skill Score" - his potential taking age and experience into consideration - through 2022-2024 is fairly consistent - a drivers skill doesn't just vanish overnight. Yes, there's a slight decline as he's aging, but nothing major, yet. Now if we look at Tsunoda's and Lawson's graphs we can agree with Red Bull's management on prefering the young kiwi. Lawson's skill level would likely match Perez's by the middle of 2025. Tsunoda's improvement seems much more sluggish and his ceiling is definitely lower.  

Now, if we look at the yearly "Performance Over Expectation" (POE) metric though, which measures how a driver performs against the model's race-by-race predictions, it's obvious that Perez **was** in a downward spiral.

<!-- PLOT:yearly_poe_trend -->

Pérez's average POE dropped 0.4 standard deviation over 2 years, signifying a consistent pattern of underperformance relative to what the model expected. Tsunoda's performance was much more boring - he delivered the mediocre results that is expected from him. And Lawson? After a promising cameo in 2023 his 2024 was quite Tsunoda-esque delivering results that met, but did not significantly exceed, expectations.

**So to sum up** 

Red Bull had 3 options by the end of 2024:
1) Keep the high(ish) ceiling, high experience but at the same time high paycheck and low confidence Perez
2) Promote the low ceiling, so-so performing, so-so paycheck Tsunoda
3) Promote the higher potential, low experience, OK
 performing rookie Lawson with the low paycheck

**Based on our data I think the conclusion is that Red Bull made the right decision to part ways with Pérez and to promote Lawson instead of Tsunoda.**

### Part B: The Two-Race Gamble on Liam Lawson
Yet, after just two races in the Red Bull, Lawson was replaced by... Yuki Tsunoda?!
This decision is far harder to justify with data. Two races is an insufficient sample size to judge any driver, especially one adapting to a new car and immense pressure. As our "All-Time Skill" chart showed, Lawson possesses a stronger underlying talent, definitely greater than Tsunoda.
Sidelining him so quickly appears to be a reaction based on immediate, short-term results rather than a belief in the long-term data. It's possible that off-track factors or specific performance clauses were at play, but from a pure talent and potential perspective, the decision to replace Lawson so hastily seems premature and questionable.
This move highlights a larger strategic oversight. Red Bull could not realistically get much more from Tsunoda—and indeed they don't. Instead of the chaotic swap at the main team, the smarter play would have been to use the junior team for what it's for: evaluation. They could have used Tsunoda as the established reference and let Isack Hadjar race alongside him. This would have allowed them to compare Hadjar to a known benchmark and not to another rookie, whose performance might be much more volatile.
By making this choice, they not only gave up on Lawson prematurely but also missed the optimal chance to properly evaluate the next driver in the pipeline. Looking at the season now, I think after 17 races it is safe to say that from the four candidates, Isack Hadjar is the worthiest.

### The Final Verdict

The data provides a nuanced view of Red Bull's turbulent driver strategy:
-   **Pérez's dismissal was a logical, albeit difficult, decision** driven by a tangible drop in performance.
-   **Lawson's swift replacement appears to be hasty**, a decision based on a sample size too small to be meaningful, especially given his potential.

Meanwhile, with Isack Hadjar impressing in the Racing Bulls, the pressure from the Red Bull pipeline remains as intense as ever.