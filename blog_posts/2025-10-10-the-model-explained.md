### Welcome to the F1metrix data analytics blog.
**Let’s start with several disclaimers.**
1) Yes, it’s a ripoff of the fantastic [f1metrics](https://f1metrics.wordpress.com/) blog by Dr. Andrew Philips which is sadly abandoned.
2) I’m not a PHD level statistician, only a hobbyist. In fact I’d be immensely grateful if someone could review my model/script.
3) Yes, I use Gemini 2.5 Pro to support me - it still took surprisingly long to get here, and it’s far from finished…
4) The underlying model is a slightly modified amalgamation of [Dr. Andrew Bell et als. work](https://research-information.bris.ac.uk/ws/portalfiles/portal/70290855/F1_paper_Mar16.pdf) and Dr. Andrew Philips’ updated model.
I fetched the training data from [f1db](https://github.com/f1db) - thank you for their hard work!
5) It's a mathematical model, which means it's an approximation of reality and has some shortcomings. I'll try to improve it (for example by handling customer cars and DNFs) but it will never be perfect. It's just a crutch that helps understand this fascinating sport better.

I try to make this blog a bit more user friendly and interactive. Readers can explore the model's results and historical through charts and data tables.

**Now that’s settled let’s see how the model works!**

#### Quantifying Greatness**: How Our F1 Model Separates Driver Skill from Car Performance
The central, unresolved debate in Formula 1 has always been the same: how much of a driver's success is due to their personal talent, and how much is simply the car they drive? Could a legendary driver win in a midfield car? How much faster would an average driver be in a championship-winning machine?
Simply looking at wins or points is insufficient. A 10th-place finish by Fernando Alonso in a 2001 Minardi was a monumental achievement, while a 2nd-place finish in a 2016 Mercedes was a relative disappointment. To have a meaningful discussion, we need a way to isolate the driver's contribution.
This post introduces our statistical model, designed to do exactly that. We will explain how it works, what its outputs mean, and how to translate its statistical findings into tangible, on-track performance.
#### The Model's Approach: Slicing the "Success Pie"
Think of any race result as a "pie" of success. Our model's job is to slice up that pie and assign a piece to every factor that contributed. It is a Bayesian hierarchical model built with PyMC, which in simple terms, means it learns a plausible range of values for each factor's contribution simultaneously.
The main slices of the pie are:

*Pure Driver Skill*: An innate, baseline talent that a driver carries throughout their career.

*Car Performance*: The specific strength or weakness of a team's car in a single season.

*Team Strength*: The underlying, long-term engineering and operational quality of a constructor.
*Contextual Factors*: The driver's age, their recent F1 experience, and crucially, their starting grid position for that race.
By accounting for every other slice, the model can isolate the piece of the pie that belongs to the driver.
#### The "Ruler" of Performance: What the Model Measures
The model does not predict finishing position directly. The performance gap between 1st and 2nd is massive, while the gap between 15th and 16th is negligible. To account for this, the model first converts race results onto a standardized statistical scale called `rankit_points`.
Think of this scale as a *performance scorecard* for every race. A score of 0.0 is a perfectly average performance for that race.
A score of +1.0 represents a great performance, one standard deviation above the average. This is a "Driver of the Day" level drive.
A score of -1.0 represents a poor performance, one standard deviation below the average.
This gives us a consistent "ruler" to measure every driver's performance in every race, regardless of the era or circumstances.
#### The Key Metric: Pure Driver Skill (`u0`)
The most important output of the model is the u0 parameter, which represents a driver's pure, innate skill. This is the "talent bonus" they bring to the table before any other factor is considered.
When looking at our all-time rankings, you may notice that the top-ranked driver, Alain Prost, has a u0 score of around +0.3. This number seems small, which leads to a crucial point about the model's design: the model is deliberately skeptical and **gives credit to the car first**.
Because drivers like Prost, Senna, and Schumacher drove some of the most dominant cars in history, the model attributes a huge portion of their success to the machinery. The u0 score represents the talent that remains after the massive advantage of the car has been accounted for. A score of +0.3 is not small; on the model's compressed scale, it is the largest talent signature it found among any driver in history.
#### From Statistics to the Track: What +0.3 u0 Means in a Race
So, how do we translate Prost's u0 of +0.3 into something meaningful on track? We can run a thought experiment.
Take a perfectly average midfield car. On its own, with a perfectly average driver (u0 = 0.0), this car is quick enough to qualify and finish in 10th place.
##### The Logic:
The key is understanding the distribution of performance in the midfield. The performance gaps are incredibly small. A few tenths of a second per lap separate multiple positions.

In a typical F1 race, the standard deviation of our `rankit_points` performance metric is roughly 0.8 to 1.0. This means a driver performing at +1.0 is significantly ahead of the pack. In the tightly packed midfield, a small gain in performance score leads to a significant gain in position. A performance score of +0.1 might secure 10th, +0.2 might be good for 9th, +0.3 for 8th, and +0.4 for 7th.
Our average driver in the average car puts in a performance that gets them to 10th place. Prost, with his innate +0.3 skill advantage, elevates that entire package. His personal input adds +0.3 to the final performance score. This is enough to leapfrog the small gaps in the midfield.
Instead of finishing 10th, his talent pushes the car up to an expected finishing position of around 7th place. Therefore, we can conclude that a u0 skill advantage of +0.3 is worth approximately 2-3 positions per race in an average car.
**The Bottom Line: The Championship Points Advantage**
This is where the true value of elite talent becomes clear.
An average driver finishing in 10th place scores 1 championship point.
Alain Prost, by using his +0.3 talent to finish in 7th place, scores 6 championship points.
The difference, attributable only to his skill, is +5 points per race.
Over a 23-race season, this translates to an advantage of approximately ***115 championship points***. This is the concrete value of greatness. It is an advantage large enough to swing any championship battle and demonstrates how a truly elite driver's talent is one of the most powerful forces in Formula 1.
#### Beyond Raw Talent: Modeling the F1 Driver Career Arc
However, a driver's performance is not static. A simple, all-time ranking of innate talent (u0) is a good starting point, but it doesn't tell the whole story. Drivers evolve, improve, and eventually decline.
Our model is designed to capture this career trajectory by incorporating a second crucial parameter: `u1`, which represents a driver's individual skill trend. This parameter captures a driver's personal rate of improvement or adaptation, separate from the typical age and experience curves the model also learns.
This allows us to distinguish between two archetypes:
The "Natural": A driver with a sky-high innate talent (u0) who enters the sport already near their peak. Their greatness lies in their consistency and incredibly high performance floor.
The "Technician": A driver with immense talent who also shows a relentless, data-driven capacity for improvement (a high u1). Their greatness lies in their ability to sand off every rough edge of their craft, raising their own performance ceiling over time.
This distinction resolves a potential contradiction: a driver like Prost might possess the highest innate talent, while a driver like Verstappen, through relentless refinement, could achieve a higher peak performance score during his prime. The model allows for both to be true.
In our next posts, we will dive deeper into these year-by-year rankings, explore the greatest single-race performances in history, and see how these career arcs play out for the legends of the sport.